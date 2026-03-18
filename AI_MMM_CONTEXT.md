# AI_MMM_CONTEXT.md — Complete MMM Algorithm Reference for AI Agents

> **Purpose:** This document provides every detail an AI agent needs to understand, debug, modify, or extend the MMM (Money Mind & Method) algorithm and its WebUI implementation. **This is the single source of truth** — all information from `MMM_robustv2.md` (26 fixes) is incorporated here.
>
> **Last Updated:** March 18, 2026
> **Status:** All phases complete. All 26 robustv2 hardening fixes implemented. Perpetual Futures Delta Hedge module (Task #26) live. Lot Lifecycle (M1/M2/M3) system added. **Split Ledger (frozen lot capacity relief) fully implemented.** March 2026 audit fixes complete (T1–T4, see §15). **Operator Strike Controls (Set Active Strike + Close Strike + Position Inject) fully implemented — see §16.** **Wind-down / regime interference fixed (March 12, 2026) — see §2.12 note.** **ATM Shield (proactive close & retreat at ATM proximity) fully implemented — see §2.20.** **Multi-DTE Support (0DTE → 5DTE+) — DTE presets, aggregate PnL safety, liquidity gate, v2 adaptive interval, v2 theta acceleration, v2 near-expiry — see §17.** **Breakeven Engine (risk-aware lot scaling by portfolio P&L boundary distance) fully implemented — see §2.21.** **Gamma Detector Engine (portfolio curvature boundary scanning, observation-only) fully implemented — see §2.22.** **Trade Transparency System (institutional-grade write-once audit trail — every fill, every P&L, every state change) fully implemented — see §18.** Production-ready.
> **Robustv2 Audit:** 25/25 fixes + 1 new feature = 26/26 complete. See §2.15 for full summary.
> **Lot Lifecycle:** M1 Profit Harvesting + M2 Lot Recycling + M3 Asymmetry Rebalancing — see §2.18.
> **Split Ledger:** Phase 1 (core cap fix) + Phase 2 (shift-time recycle) + Phase 3 (dashboard) + Profitability Suggestions — see §2.19.
> **ATM Shield:** Proactive close + full position shift + loss recovery when spot approaches active strike — see §2.20.
> **Operator Strike Controls:** Set Active Strike, Close Strike (manual buyback + re-establish farther OTM), Operator Position Inject — see §16.
> **Multi-DTE:** DTE presets (0DTE/5DTE), aggregate PnL safety, chain liquidity gate, v2 adaptive/theta/near-expiry scaling — see §17.
> **Remaining Hardening:** See `MMM_10_OF_10_PRODUCTION_PLAN.md` for 19 additional issues found in post-robustv2 audit.

---

## 1. WHAT IS MMM?

MMM is a **BTC options premium selling algorithm** (0DTE and multi-DTE) with automatic adjustment. It:

1. **Sells** both CE (call) and PE (put) options on BTC at OTM strikes
2. **Monitors** premiums adaptively (60s–1200s depending on trigger proximity)
3. **Adjusts** when one side's premium rises above its trigger — sells more of the opposite side to cover the loss
4. **Shifts strikes** when opposing premium is too low to provide meaningful hedge
5. **Closes positions at ≤5** premium to lock profit (dynamic threshold during wind-down)
6. **Handles reversals** by computing actual adjustment P&L before hedging
7. **Wind-down mode** gracefully closes positions in the final hours before expiry
8. **Safety mechanisms** protect against runaway losses, whipsaw, margin exhaustion
9. **Adopt mode** imports live exchange positions into MMM without manual entry
10. **Regime controls** block adjustments during IV spikes, extreme gamma, or strong price trends
11. **Margin guardian** monitors real exchange margin utilization and enforces tier-based defense
12. **Circuit breaker** isolates exchange API failures gracefully without terminating sessions
13. **Lot lifecycle** harvests profitable frozen positions (M1), recycles capped-out positions into better strikes (M2), and boosts harvesting when call/put imbalance is extreme (M3)
14. **Split Ledger** frees frozen positions from blocking the active position cap — only `active_lots` count against `max_lots_per_side`, with `max_total_exposure` as a safety ceiling on combined active+frozen
15. **Shift-Time Recycle** proactively closes cheap frozen positions at each strike shift, folding buyback cost into the new sell lot calculation
16. **Operator Strike Controls** — three manual intervention tools on the Positions tab:
    - **Set Active Strike (📌):** Switch the algo's monitoring focal point to any open strike without placing any order
    - **Close Strike (🔴):** Buy back ALL lots at a chosen strike (exchange order), remove from ledger; if active_strike is closed, the remaining open strike with most lots auto-promotes
    - **Operator Position Inject (💉):** Sell new lots at any strike and register them in the algo ledger
    - Enables the operator workflow: close a near-ATM risk strike → inject at a safer far-OTM strike → reduces perp futures usage
17. **ATM Shield** — automated proactive defense: when spot approaches within `atm_shield_proximity_pct` of an active strike, the algo pre-emptively closes all active positions on that side and re-establishes them at a safer OTM strike. Full position shift (original lots preserved) + loss recovery lots + sympathetic rebalance of the safe side.
18. **Multi-DTE support** — DTE presets (0DTE, 5DTE) auto-configure parameters for different expiry horizons. Aggregate PnL safety prevents combined losses across sessions from exceeding a global limit. Liquidity gate blocks session creation on illiquid expiry chains. Adaptive interval v2 and theta acceleration v2 scale by percentage-of-DTE instead of absolute hours. Near-expiry v2 adds wind-down zone warnings for multi-DTE sessions.
    - **Set Active Strike (📌):** Switch the algo's monitoring focal point to any open strike without placing any order
    - **Close Strike (🔴):** Buy back ALL lots at a chosen strike (exchange order), remove from ledger; if active_strike is closed, the remaining open strike with most lots auto-promotes
    - **Operator Position Inject (💉):** Sell new lots at any strike and register them in the algo ledger
    - Enables the operator workflow: close a near-ATM risk strike → inject at a safer far-OTM strike → reduces perp futures usage

The complete calculation logic is defined in `MONEY_POWER_CALCULATION_LOGIC.md` (22 sections). The development plan is in `MMM_DEVELOPMENT_PLAN.md` (all phases complete). The comprehensive audit is in `MMM_robustv2.md` (26 items, all implemented). The remaining hardening plan is in `MMM_10_OF_10_PRODUCTION_PLAN.md`.

---

## 2. ALGORITHM CORE LOGIC

### 2.1 Entry (Section 3)

**Mode A — Fresh:** User provides desired CE/PE premium + lots + expiry → algo scans the options chain → finds OTM strikes closest to desired premium → user confirms → positions sold.

**Mode B — Import:** User enters existing CE/PE strike, fill price, lots → algo initializes state without placing orders.

**Mode C — Adopt:** Fetches open short BTC options from Delta Exchange (`mmm_adopter.py`), user selects positions → algo maps them to active/frozen state per side and initializes without placing orders. Trigger snapshots default to current prices ("take over from NOW").

### 2.2 Heartbeat Loop (Section 4)

Every `interval` seconds (adaptive: 60–1200s, see §2.10):

```
1. Fetch CE premium at active_ce_strike → CE_now
2. Fetch PE premium at active_pe_strike → PE_now
3. Run Close-at-5 on ALL positions (active + frozen)
   — if wind-down mode active, use elevated threshold (§2.11)
3a. Run Profit Harvesting (M1) — scan for harvestable frozen positions (§2.18)
    — M3 Asymmetry Rebalancing modifies thresholds if call/put imbalance is extreme
    — Guarded by is_wind_down_active() — does NOT run during wind-down
4. Run Safety Checks (mmm_safety.py)
5. Run Regime Checks (mmm_regime.py) — abort adjustment if regime blocks
6. If status ≠ RUNNING → skip adjustment logic
7. Run Margin Guardian check (mmm_margin_guardian.py) — block sells if YELLOW+
8. Compute excess: ce_excess = CE_now - trigger_snapshot[active_ce_strike]
9. Apply min_trigger_move filter (PERCENTAGE-BASED):
   ce_threshold = trigger_snapshot × (min_trigger_move_pct / 100)
   ce_triggered = ce_excess > ce_threshold
10. Four outcomes:
    A) Neither triggered → DO NOTHING
    B) CE triggered only → CE is aggressor, sell PE (Section 5)
    C) PE triggered only → PE is aggressor, sell CE (Section 5)
    D) Both triggered → PAUSE, show both-sides alert (Section 8)
11. If adjustment results in "Position cap reached" on hedge side:
    → Trigger M2 Lot Recycling (§2.18) — two-phase atomic recycle operation
```

### 2.3 Adjustment Calculation (Section 5)

For **CE as aggressor** (PE mirror is identical with CE↔PE swapped):

**Step 1 — Reversal check:**
```
reversal = (last_aggressor == "PE" AND CE is now aggressor)
```

**Step 2 — Loss calculation:**

- **Standard (continuation/first-ever):**
  Compute total loss across ALL open positions on the aggressor side:
  $$L_{\text{active}} = (CE_{now} - trigger_{CE}) \times N_{active\_CE}$$
  $$L_{\text{shifted}} = \sum_{j} \max\bigl((P_{current,j} - P_{entry,j}) \times N_j, \; 0\bigr)$$
  $$L = L_{\text{active}} + L_{\text{shifted}}$$
  ALL positions at ALL strikes contribute. No position is ever excluded.

- **First reversal:** Compute actual P&L of ALL CE adjustment fills (active + shifted):
  $$L = \left|\sum_{i} (P_{entry,i} - P_{current,i}) \times N_i\right|$$
  Only triggers if sum is negative (adjustments underwater). If ≥ 0 → DO NOTHING.

**Step 3 — Strike check:**
If opposing premium < `shift_threshold` → Strike Shift (Section 10)

**Step 4 — Lots calculation:**
$$N_{sell} = \left\lceil \frac{L}{P_{hedge}} \times (1 + buffer) \right\rceil$$

**Step 4a — Breakeven multiplier (if enabled, added Mar 15, 2026):**
- Compute portfolio breakeven points (cached, recomputed only on position change)
- Classify current spot into zone: SAFE / WARNING / DANGER / CRITICAL
- Apply aggression multiplier: 1.0× / 1.0–1.3× / 1.3–2.0× / 2.0–3.0×
- Combined multiplier ceiling enforced: max 3.0× total (gamma × breakeven × trend)

**Step 5 — Execute sell, record fill, update BOTH trigger snapshots**

### 2.4 Trigger System (Section 7)

Triggers create a **safe zone**. After each adjustment, BOTH sides' snapshots update to current prices:
```
ce_trigger_snapshot[active_ce_strike] = CE_now
pe_trigger_snapshot[active_pe_strike] = PE_now
```

The trigger means: "All losses up to this premium level are already covered."

### 2.5 Strike Shifting (Section 10)

When opposing premium is below `shift_threshold`:
1. Scan options chain for strikes with premium ≥ threshold
2. Pick strike whose premium is closest to `shift_target_premium` (default 100)
3. Move old positions to `shifted_positions` (not closed — still fully tracked and included in ALL loss calculations)
4. Set new `active_strike`, sell at new strike
5. ALL positions (active + shifted) are used in the standard adjustment formula — no position is ever excluded

**CRITICAL:** The `shift_threshold` only controls WHERE to open new positions. It never makes existing positions invisible. The internal code uses the variable name `frozen_positions` for backward compatibility, but these positions are NOT frozen — they are live risk.

### 2.6 Close-at-5 (Section 11)

Every interval, scan ALL positions. If premium ≤ `close_at_threshold`:
- Buy back at market/ask
- Record realized P&L: `(entry_premium - close_premium) × lots`
- Remove from tracking
- If ALL positions closed on both sides → strategy COMPLETE

### 2.7 Both-Sides-Up (Section 8)

When BOTH CE and PE exceed triggers simultaneously:
- Set status = `BOTH_SIDES_UP`
- Show alert modal with 4 options: ADD / REDUCE / RESUME / STOP
- Algo pauses until user decides

### 2.8 Safety Mechanisms (Sections 13-14)

| Safety | What It Does |
|--------|-------------|
| Position Cap | Max **active** lots per side (default 100). Split Ledger: only `active_lots` count — frozen lots excluded. |
| Max Total Exposure | Absolute ceiling on active+frozen lots per side (default auto: 2× `max_lots_per_side`). Prevents runaway accumulation when frozen lots no longer block the cap. Error string "Total exposure ceiling" — does NOT trigger M2. |
| Max Adjustments | Counter limit (default 30) |
| Max Loss | Hard stop — close all if P&L < -max_loss |
| Adaptive Whipsaw Guard | Score-based graduated response (NORMAL→CAUTION→RESTRICT→COOLDOWN). Replaces old binary pause. See §2.8b. |
| Position Asymmetry | Warn at 3:1, alert at 5:1 ratio (uses `total_lots` — includes frozen) |
| Near-Expiry | Stop adjustments at 15min, auto-close at 5min |
| Margin Check | Verify margin before every sell (uses `total_lots` — includes frozen) |
| Trailing Profit | Protect peak P&L (stop at 50% drawdown from peak) |
| Theta Acceleration | Widen triggers near expiry (let theta work) |
| P&L Guardrail | Warn/pause/stop at loss thresholds |
| Periodic Reconciliation | True P&L check every 5 adjustments |

#### 2.8b Adaptive Whipsaw Guard (Mar 2026)

Replaces the old binary whipsaw pause (`_whipsaw_paused_at` → manual resume) with a score-based graduated response that automatically throttles and recovers.

**Score levels:**
| Score | Level | Effect |
|-------|-------|--------|
| 0-1 | NORMAL | No restrictions |
| ≥ `whipsaw_caution_score` (2) | CAUTION | Triggers widened 1.5× |
| ≥ `whipsaw_restrict_score` (3) | RESTRICT | Triggers widened 2.0× + lots halved |
| ≥ `whipsaw_cooldown_score` (4) | COOLDOWN | Skip one interval, score -2 |

**Noise detection:** A direction flip-flop counts as noise only if (a) it's within the `whipsaw_window_mins` rolling window AND (b) the spot move was < `whipsaw_spot_move_pct`. Genuine large moves don't penalize.

**Score decay:** -1 per adjustment_interval with no noise detected.

### 2.9 User Parameters (Section 19)

| Parameter | Default | Hot Reload? |
|-----------|---------|-------------|
| `desired_ce_premium` | User input | No |
| `desired_pe_premium` | User input | No |
| `initial_lots` | User input | No |
| `expiry` | User input | No |
| `adjustment_interval` | 300s | **Yes** |
| `min_trigger_move_pct` | 3% | **Yes** |
| `shift_threshold` | 50 | **Yes** |
| `shift_target_premium` | 100 | **Yes** |
| `close_at_threshold` | 5 | **Yes** |
| `premium_buffer_pct` | 5% | **Yes** |
| `max_lots_per_side` | 100 | **Yes** |
| `max_adjustments` | 30 | **Yes** |
| `max_loss_amount` | User-defined | **Yes** |
| `stop_adjustment_mins` | 15 | **Yes** |
| `auto_close_mins` | 5 | **Yes** |
| `cooldown_on_reversal` | true | **Yes** |
| `whipsaw_limit` | 3 | **Yes** | *(DEPRECATED — kept for compat, replaced by score-based params below)* |
| `whipsaw_window_mins` | 30 | **Yes** |
| `whipsaw_spot_move_pct` | 0.3 | **Yes** |
| `whipsaw_caution_score` | 2 | **Yes** |
| `whipsaw_restrict_score` | 3 | **Yes** |
| `whipsaw_cooldown_score` | 4 | **Yes** |
| `trailing_stop_pct` | 50% | **Yes** |
| `adaptive_interval_enabled` | true | **Yes** |
| `adaptive_max_interval` | 1200 | **Yes** |
| `wind_down_enabled` | true | **Yes** |
| `wind_down_minutes` | 120 | **Yes** |
| `wind_down_threshold_pct` | 25 | **Yes** |
| `wind_down_floor_action` | stop_adjustments | **Yes** |
| `wind_down_on_atm` | false | **Yes** |
| `harvest_enabled` | true | **Yes** |
| `harvest_profit_pct` | 40.0 | **Yes** |
| `harvest_min_age_mins` | 30 | **Yes** |
| `harvest_max_per_beat` | 3 | **Yes** |
| `harvest_pressure_threshold` | 0.5 | **Yes** |
| `recycle_enabled` | true | **Yes** |
| `recycle_min_premium_ratio` | 2.5 | **Yes** |
| `recycle_premium_ceiling` | 50.0 | **Yes** |
| `recycle_max_pct` | 0.50 | **Yes** |
| `recycle_cooldown_sec` | 300 | **Yes** |
| `recycle_min_lot_gain` | 5 | **Yes** |
| `recycle_free_lot_buffer` | 10 | **Yes** |
| `recycle_protect_original` | true | **Yes** |
| `rebalance_enabled` | true | **Yes** |
| `rebalance_asymmetry_threshold` | 5.0 | **Yes** |
| `rebalance_pressure_threshold` | 0.8 | **Yes** |
| `max_total_exposure` | 0 (auto: 2× max_lots_per_side) | **Yes** |
| `shift_recycle_enabled` | false | **Yes** |
| `shift_recycle_premium_floor` | 60.0 | **Yes** |
| `shift_recycle_max_pct` | 1.0 | **Yes** |
| `shift_recycle_floor_ratio` | 0.40 | **Yes** |
| `atm_shield_enabled` | false | **Yes** |
| `atm_shield_proximity_pct` | 0.5 | **Yes** |
| `atm_shield_target_otm_pct` | 1.0 | **Yes** |
| `atm_shield_loss_split_aggressor` | 0.3 | **Yes** |
| `atm_shield_max_per_session` | 3 | **Yes** |
| `atm_shield_cooldown_mins` | 10 | **Yes** |
| `breakeven_control_enabled` | false | **Yes** |
| `breakeven_warning_pct` | 2.0 | **Yes** |
| `breakeven_danger_pct` | 1.0 | **Yes** |
| `breakeven_critical_pct` | 0.5 | **Yes** |
| `breakeven_aggression_max` | 3.0 | **Yes** |
| `breakeven_scan_range_pct` | 5.0 | **Yes** |
| `max_combined_lot_multiplier` | 3.0 | **Yes** |
| `breakeven_narrow_band_threshold` | 5.0 | **Yes** |

"Hot Reload = Yes" means the parameter can be changed via WebUI while the algo is running and takes effect on the next heartbeat interval.

### 2.10 Adaptive Heartbeat Interval (Added Feb 17, 2026)

The heartbeat interval dynamically adjusts based on trigger proximity:

| Condition | Interval | Rationale |
|-----------|----------|----------|
| ≥80% of trigger exceeded | 60s | Action imminent |
| ≥50% exceeded | 120s | Getting close |
| ≥30% exceeded | 180s | Moderate movement |
| <30% exceeded | User-set interval | Normal monitoring |
| Both premiums declining | 600–1200s | Premiums moving favorably, relax |

**Implementation:** `mmm_trigger.py` → `compute_adaptive_interval()` with `ADAPTIVE_INTERVAL_TIERS`.

### 2.11 Wind-Down Mode (Added Feb 17, 2026)

Activates when `minutes_to_expiry ≤ wind_down_minutes` (default 120 = 2 hours):

1. **Elevated close threshold**: Closes positions at premium ≤ `entry_premium × (wind_down_threshold_pct / 100)` instead of static 5
2. **LIFO order**: Closes most recently added positions first
3. **Floor action**: If positions can't be closed, executes `wind_down_floor_action` (stop_adjustments / close_all / alert)
4. **ATM auto-trigger** (`wind_down_on_atm`): When ON, wind-down is automatically activated the moment any **original** strike becomes ATM (spot within 0.5% of entry strike). This is a gentler alternative to `close_at_atm` — instead of an immediate close-all, the algo switches to gradual LIFO buyback. The session flag `_atm_wind_down_triggered` is set once and persists for the session. Checked in `is_wind_down_active()` in `mmm_wind_down.py`.

**Implementation:** `mmm_wind_down.py` + `mmm_monitor.py` (ATM detection block before `close_at_atm` check) + `mmm_config.py` + `MMMSettingsDialog.js`.

### 2.12 Regime Controls (Added Feb 20, 2026)

Three pre-adjustment controls checked every heartbeat BEFORE trigger evaluation:

**A. Volatility Regime Filter** — detects IV spikes + realized volatility. States: `NORMAL`, `ELEVATED`, `HIGH`. When HIGH, blocks new adjustments.

**B. Portfolio Gamma Cap** — enforces dollar-gamma limits. States: `NORMAL`, `SOFT`, `HARD`, `EMERGENCY`. Blocks adjustments when gamma exposure is too large.

**C. Trend Detection Guard (Tiered — 4-tier graduated response)** — detects directional BTC moves from session anchor using a 4-tier escalation system:

| Tier | Name | Threshold | Action | EMA Required? |
|------|------|-----------|--------|---------------|
| 0 | NORMAL | — | No action | — |
| 1 | ALERT | `trend_tier1_pct` (0.5%) | Lot reduction by `trend_tier1_lot_reduction` (30%) | Yes (or acceleration bypass) |
| 2 | GUARD | `trend_tier2_pct` (1.0%) | Block dangerous-side sells (CE in up-trend, PE in down-trend) | No |
| 3 | BLOCK | `trend_tier3_pct` (1.5%) | Block ALL new sell orders | No |
| 4 | WIND-DOWN | `trend_tier4_pct` (2.0%) | Auto-trigger wind-down (no operator confirmation) | No |

**Tier behavior:** Tiers only escalate (never de-escalate within a trend). Reset is binary — retracement + calm beats → Tier 0. Price crossing anchor → immediate reset.

**Acceleration check:** If BTC moves `trend_acceleration_pct` within `trend_acceleration_window_s`, Tier 1 can fire without EMA confirmation (fast-move bypass). Reuses existing `_vol_spot_history` ring buffer.

Aggregate actions: `NORMAL` (proceed), `WARN` (Tier 1 — lot reduction), `BLOCK_CE/PE_SELLS` (Tier 2 — directional block), `BLOCK_ALL_SELLS` (Tier 3), `FORCE_REDUCE` (Tier 4 — auto wind-down).

**Wind-down + Regime interaction (Fixed March 12, 2026):** `BLOCK_ALL_SELLS` blocks new *sells* only. If wind-down is simultaneously active (e.g. Tier 4 or vol-HIGH sets `_trend_wind_down_triggered`), trigger evaluation is **not skipped** — the heartbeat continues to OUTCOME_CE/PE so the existing `blocked + is_wind_down_active → _process_wind_down_buyback()` path at line ~1786 can execute buybacks. Without this, `BLOCK_ALL_SELLS` set `_skip_to_pnl = True` which bypassed the entire trigger block, silently preventing any wind-down from acting. Note: proactive wind-down (every heartbeat regardless of trigger) is intentionally NOT used — it was previously removed for causing unintended position erosion.

**Implementation:** `mmm_regime.py` + monitor heartbeat + `MMMRegimePanel.js` (frontend).

### 2.13 Margin Guardian (Added Feb 20, 2026)

Queries Delta Exchange for real margin utilization every heartbeat. Enforces tier-based defense:

| Tier | Threshold | Action |
|------|-----------|--------|
| GREEN | < green_pct | Normal operation |
| YELLOW | ≥ yellow_pct | Block new sells, log caution |
| ORANGE | ≥ orange_pct | Force auto wind-down (aggressive buyback) |
| RED | ≥ red_pct | Emergency reduce — taker orders, close all |
| CRITICAL | ≥ critical_pct | Survival mode — close all + stop session |

Formula: `utilization% = (position_margin + order_margin) / net_equity × 100`
where `net_equity = balance + unrealized_pnl`. Sends Telegram alerts on tier escalation.

**Implementation:** `mmm_margin_guardian.py` + `mmm_telegram.py` + `MMMMarginGuardianPanel.js`.

### 2.14 Circuit Breaker (Added Feb 18, 2026)

Three-state circuit breaker protecting the heartbeat loop from exchange API failures:

| State | Behavior |
|-------|----------|
| CLOSED (nominal) | All requests pass through |
| OPEN (tripped) | Fast-fail; backoff 1-3: partial beat (close-at-5 + safety only); backoff 4+: full skip |
| HALF_OPEN (probe) | One trial request; success → CLOSED; fail → OPEN |

CLOSED → OPEN after `FAILURE_THRESHOLD = 3` consecutive failures. OPEN → HALF_OPEN after `RESET_TIMEOUT = 30s`. Never terminates the session — isolates, waits, self-heals.

**Implementation:** `mmm_circuit_breaker.py` + `mmm_monitor.py`.

### 2.15 Robustv2 Hardening (Implemented February 22, 2026)

A comprehensive audit (`MMM_robustv2.md`) identified and fixed 25 issues + 1 new feature across the entire backend. Key improvements:

#### Critical Fixes
| # | Fix | Impact |
|---|-----|--------|
| 1 | **P&L Incomplete Guard** — If >50% of position premium fetches fail, session is PAUSED instead of continuing with partial data | Prevents stale P&L from letting the session trade when it should hard-stop |
| 2 | **Calculation Incomplete Flag** — `calculate_standard_loss()` and `calculate_reversal_loss()` now return `(value, incomplete_bool)` tuples. Monitor emits `mmm_safety` event with `type='calculation_incomplete'` | UI warns user when calculations use partial data |
| 3 | **Partial Fill Rejection** — Missing `unfilled_size` returns failure instead of assuming full fill. Added NaN/Inf/negative guards | No more phantom positions from API quirks |

#### High Fixes
| # | Fix | Impact |
|---|-----|--------|
| 5 | **Position Cap Hard-Block** — `check_position_cap()` action changed from `'warn'` to `'stop_adjustments'` | Safety check actually stops adjustments at cap |
| 6 | **Trigger Snapshot Validation** — Before `evaluate_triggers()`, validates active strike key exists in snapshot. If missing/zero, initializes from exchange | No false trigger fires after restart or shift |
| 7 | **Decaying Peak P&L** — Peak decays as `0.9 * old + 0.1 * current` when P&L is below peak. Hard-resets on reversal | No stale trailing stop alerts |
| 8 | **ID-Based Position Removal** — Removed index-based removal; uses `_pos_id` for O(1) lookup or content-match fallback | Safe, performant position removal after close-at-5 |
| 9 | **Original Strike Defensive** — `scan_closeable_positions()` uses `original_strike` not `active_strike` for original lots | Future-proof against strike decoupling |
| 10 | **Reversal Case-Insensitive** — `last.upper() == 'NONE'` with type guard | No false reversals from serialization variants |
| 11 | **Re-evaluate After Close-at-5** — When close-at-5 closes positions on aggressor side, triggers re-evaluated before adjustment | Prevents over-hedging when close-at-5 relieves pressure |

#### Medium Fixes
| # | Fix | Impact |
|---|-----|--------|
| 12 | **Per-Side Premium Fallback** — One side's failure falls back to cache for that side only; other side uses fresh data | Healthy side keeps operating when one side has API issues |
| 13 | **Canonical `strike_key()`** — `mmm_constants.py` exports `strike_key(float) -> str` via `str(int(round(float(strike))))` | No trigger snapshot key mismatches |
| 14 | **Timezone-Aware UTC** — All `datetime.utcnow()` → `datetime.now(timezone.utc)`. Timestamps now include `+00:00` suffix | Correct wind-down/expiry timing; no IST offset bugs |
| 15 | **Param Interdependency Validation** — Validates relationships: `wind_down ≥ close_at`, margin tier ordering, `max_adj ≥ whipsaw`, etc. | Bad config combos rejected on hot-reload |
| 16 | **Atomic Activity Log** — Write `.tmp` → `fsync()` → `os.rename()`. Buffer increased to 500. Throttle reduced to 1-in-2 | Crash-safe log, more data preserved |
| 17 | **WebSocket Failure Counter** — `_consecutive_failures` counter, `get_ws_health()` function. CRITICAL log at 10 consecutive failures | Detects stale UI condition |
| 18 | **Both-Sides Fresh Re-Fetch** — Re-fetches premiums before auto-decision instead of using 30s-stale data | Auto-decision hedges the correct side |

#### Low/Architectural Fixes
| # | Fix | Impact |
|---|-----|--------|
| 19 | **Decimal Arithmetic** — `_D(x)` helper converts via `str(x)` to avoid IEEE 754 errors. Used in all P&L accumulation paths | Eliminates $0.50-$1.00 drift over session lifetime |
| 20 | **Session ID Fallback** — UUID hex[:8] (4.3B combinations) instead of [:4] (65K) | No session ID collisions |
| 21 | **Theta Acceleration Cap** — `min(base * 2, 80.0)` hard cap | Triggers can still fire even near expiry |
| 22 | **fill_price Guard** — `try/except (ValueError, TypeError)` + `isnan`/`isinf` | No crash on malformed API response |
| 23 | **Unified Position Ledger** — `positions[]` list is authoritative source. `recompute_side_lots()` rebuilds all computed views. Auto-migration. ID-based removal | Single source of truth for positions; 50+ read sites unchanged |
| 24 | **Derived State Consistency** — Assertion at heartbeat start verifies `total_lots == computed total`. Auto-repairs on mismatch | Catches any mutation that forgot `recompute_side_lots()` |

### 2.16 Perpetual Futures Delta Hedge (Implemented February 22, 2026)

**New File:** `mmm_perp_hedge.py` (441 lines)

Hedges directional risk with BTC perpetual futures (BTCUSD). Perps are linear (zero gamma) — they absorb directional moves without adding gamma exposure.

**How it works:**
1. Every heartbeat, `_calculate_portfolio_delta()` computes net portfolio delta across ALL positions
2. If `|effective_delta| > perp_hedge_delta_threshold` (default 0.02), hedge is needed
3. Calculates target perp lots to bring effective delta to zero (or ratio-adjusted target)
4. Executes via existing `rest_client.place_order_by_symbol()` (BTCUSD perp)
5. Rebalances when drift exceeds `perp_hedge_rebalance_band` (default 0.005)
6. Direction flips (long↔short) are single atomic operations

**Parameters (all hot-reload):**

| Parameter | Default | Range |
|-----------|---------|-------|
| `perp_hedge_enabled` | false | bool |
| `perp_hedge_delta_threshold` | 0.02 | 0.005–0.10 |
| `perp_hedge_ratio` | 1.0 | 0.3–1.0 |
| `perp_hedge_rebalance_band` | 0.005 | 0.001–0.02 |
| `perp_hedge_max_lots` | 50 | 5–200 |
| `perp_hedge_cooldown_sec` | 30 | 10–300 |

**Safety Guards:**
- Max lots cap, cooldown timer, session-stop auto-close, orphan protection
- Delta sanity check (skips if `_pnl_calculation_incomplete`)
- Perp P&L included in max-loss and trailing-stop total
- Stale-delta guard — skips hedge when P&L calculation is incomplete

**Interaction with MMM:** Both work simultaneously (institutional approach). Adjustments collect theta, perp hedges delta. Regime may block adjustments but NOT perp hedge — it's the primary defense when regime blocks.

**WebSocket Events:** `mmm_perp_hedge_update` (every heartbeat), `mmm_perp_hedge_execution` (on trade), `mmm_perp_hedge_flip` (on direction flip)

**Exit:** Perp closes on wind-down, max-loss, trailing stop, all-positions-closed, manual stop, or expiry.

### 2.17 Frontend Timezone-Aware Date Parsing (Fixed February 22, 2026)

Fix #14 changed backend timestamps from `datetime.utcnow()` (naive UTC, no suffix) to `datetime.now(timezone.utc)` (timezone-aware, `+00:00` suffix). This caused a cascading frontend crash — all 11 locations that appended `'Z'` to timestamps now created invalid strings like `2026-02-22T13:07:22+00:00Z`.

**Fix:** Added `parseUTC(ts)` utility in `mmmFormatters.js` and `MMMStatusBanner.js`:
- Checks if timestamp `endsWith('Z')` or matches `/[+-]\d{2}:\d{2}$/`
- If timezone-aware → parse directly
- If naive UTC → append 'Z' then parse
- Returns null for invalid
- Fixed 6 frontend files, 11 locations total

### 2.18 Lot Lifecycle — M1/M2/M3 (Added March 3, 2026)

Three mechanisms that manage the lifecycle of frozen positions beyond simple close-at-5. Designed to work together, configurable independently via 15 hot-reloadable params.

**M1 — Profit Harvesting** (`mmm_harvester.py`):
- Runs in heartbeat Step 3a, after close-at-5 but BEFORE safety checks
- Scans frozen positions where profit ≥ `harvest_profit_pct`% AND age ≥ `harvest_min_age_mins`
- Only activates when capacity pressure ≥ `harvest_pressure_threshold` (lots_used/max_lots)
- Caps at `harvest_max_per_beat` closes per heartbeat cycle
- Positions scored by `harvest_score = profit_pct × age_score × premium_weight` for priority
- Skipped during wind-down mode (wind-down has its own close logic)
- Success increments `session['harvest_count']` and `session['harvest_lots_freed']`

**M2 — Lot Recycling** (`mmm_recycler.py`):
- Triggered when an adjustment hits "Position cap reached" (no lots available on hedge side)
- Two-phase atomic operation:
  - **Phase A:** Buyback cheapest frozen positions (via `close_position`)
  - **Phase B:** Sell fewer lots at a better (closer-to-ATM) strike (via `execute_adjustment`)
- Three viability checks must ALL pass before execution:
  1. Premium ratio: `new_premium / avg_recycle_premium >= recycle_min_premium_ratio`
  2. Net lot gain: `recycled_lots - new_lots_needed >= recycle_min_lot_gain`
  3. Affordability: `new_lots_needed + remaining_lots <= max_lots_per_side`
- Cooldown: `recycle_cooldown_sec` (300s default) between recycle attempts
- `recycle_protect_original=true` — original entry position never recycled
- Premium ceiling: only recycle positions with current premium ≤ `recycle_premium_ceiling`
- `recycle_count` increments on SUCCESS only; `recycle_attempt_count` on failure
- Only runs in GREEN/YELLOW margin tiers (blocked in ORANGE/RED/CRITICAL)

**M3 — Asymmetry Rebalancing** (`mmm_harvester.py: get_effective_harvest_params()`):
- Modifier on M1 — NOT a standalone mechanism
- When call/put lot ratio exceeds `rebalance_asymmetry_threshold` (e.g., 5:1):
  - **Extreme** (ratio > threshold): profit_pct × 0.6 (floor 20%), max_per_beat=5, pressure_threshold=0.3
  - **Moderate** (ratio > half-threshold): profit_pct × 0.8 (floor 25%), max_per_beat=4, pressure_threshold=0.5
- Only boosts harvesting on the **heavier** side to reduce imbalance
- Requires `rebalance_enabled=true` AND capacity pressure ≥ `rebalance_pressure_threshold`

**Analytics:** `mmm_analytics_storage.py` persists `total_harvests`, `total_harvest_lots`, `total_recycles`. `mmm_analytics_aggregator.py` computes per-session averages.

**WebSocket:** `mmm_harvest` and `mmm_recycle` events emitted via `mmm_websocket.py`.

**Activity Log:** `mmm_activity.py` records `harvest`, `recycle`, `shift_recycle`, `rebalance_boost` event types in `'adjustments'` category.

---

### 2.19 Split Ledger — Frozen Lot Capacity Relief (Implemented March 4, 2026)

**Problem:** When strike shifts freeze positions, frozen lots counted 1:1 against `max_lots_per_side`, progressively crippling the bot's ability to make new adjustments. After 3 shifts, only 25% of capacity might remain available for productive hedging.

**Solution: Split Ledger** — two complementary mechanisms:

#### Phase 1: Split Ledger Core

Only `active_lots` count against `max_lots_per_side` for the position cap. Frozen positions still exist, still accrue P&L, still get closed by close-at-5 — they just don't block new adjustments.

**Changes (4 files, 13 edits):**

| Component | What Changed |
|-----------|-------------|
| `mmm_engine.py` line 334 | Cap check reads `active_lots` instead of `total_lots` |
| `mmm_engine.py` lines 351-371 | New `max_total_exposure` ceiling block (uses `total_lots`) — error string "Total exposure ceiling" intentionally differs from "Position cap reached" to avoid triggering M2 |
| `mmm_safety.py` line 89 | `check_position_cap()` reads `active_lots` |
| `mmm_safety.py` line 60 | `run_all_checks()` calls new `check_total_exposure()` |
| `mmm_safety.py` lines 330-384 | New `check_total_exposure()` method — `action: 'warn'` (NOT `stop_adjustments`) |
| `mmm_recycler.py` | Param renamed `current_total_lots` → `current_active_lots`, Check 3 affordability uses `active_lots`, Phase B cap check uses `active_lots` |
| `mmm_state.py` | `DEFAULT_PARAMS`: `max_total_exposure=0`, 5 shift_recycle params. `HOT_RELOAD_PARAMS`: all 6 added |

**Do NOT touch these** (they correctly use `total_lots`):
- `mmm_engine.py` lines 100-150: `calculate_standard_loss()` — loss calc MUST include frozen
- `mmm_engine.py` lines 240-260: `calculate_reversal_loss()` — same
- `mmm_safety.py` lines 338-339: `check_asymmetry()` — asymmetry monitors total exposure
- `mmm_safety.py` lines 515-517: `check_margin()` — margin proxy must include all lots
- `mmm_recycler.py` line 329: greedy selection — `max_recycle_pct` applies to total pool
- `mmm_harvester.py` lines 50-51, 126: M1 uses `total_lots` for capacity pressure
- `mmm_perp_hedge.py` line 109: rebalance band widener uses total exposure

**M2 trigger safety:** The string `"Position cap reached"` at `mmm_engine.py` line 340 is UNCHANGED. The monitor at line 2615 checks `'Position cap reached' in constraint_msg` to trigger M2 recycling. The new `"Total exposure ceiling"` string at line 363 does NOT appear in the monitor's M2 logic.

#### Phase 2: Shift-Time Recycle

At the moment of a strike shift, optionally close cheap frozen positions BEFORE selling new lots. Buyback cost is folded into the new sell lot calculation so net coverage is the same.

**Changes (1 file, 3 edits):**

| Component | What Changed |
|-----------|-------------|
| `mmm_monitor.py` line 77 | Added `_D, _LOT` to imports from `mmm_constants` |
| `mmm_monitor.py` lines 2781-2790 | Hook in `_process_strike_shift()`: calls `_shift_time_recycle()`, folds `shift_recycle_buyback` into `total_loss_to_cover` |
| `mmm_monitor.py` lines 3392-3534 | New `_shift_time_recycle()` method — closes frozen positions with live premium below floor, cheapest first, respects `max_pct` |

**Disabled by default:** `shift_recycle_enabled=False`. When disabled, `shift_recycle_buyback = 0.0` → `total_loss_to_cover = loss + 0.0 = loss` — behavior 100% identical to pre-Split-Ledger.

**Dynamic premium floor (Suggestion 1):** When `shift_recycle_premium_floor <= 0`, floor is computed as `new_strike_premium × shift_recycle_floor_ratio` (default 0.40). Auto-adapts to current market premium levels.

**ROI tracking (Suggestion 3):** `session['shift_recycle_stats']` accumulates `{total_buyback, total_lots_freed, total_shifts}` for production tuning.

#### Phase 3: Dashboard / Frontend

Frontend updated to reflect Split Ledger semantics:

| Component | What Changed |
|-----------|-------------|
| `MMMSafetyPanel.js` | CE/PE position indicators show `active_lots` vs cap (not `total_lots`). Display shows frozen count: `40 / 100 (+60 frozen)`. Tooltip shows total exposure vs `max_total_exposure` ceiling. Asymmetry gauge kept on `total_lots` (matches `check_asymmetry()`). Asymmetry tooltip shows full breakdown. |
| `MMMTriggerGauge.js` | Already passes `activeLots`, `totalLots`, `frozenLots` correctly. No changes needed. |
| `MMMSettingsDialog.js` | Safety section: added `max_total_exposure`. Position Lifecycle section: added `shift_recycle_enabled`, `shift_recycle_premium_floor`, `shift_recycle_floor_ratio`, `shift_recycle_max_pct`. Rich `PARAM_TOOLTIPS` for all 5 new params. |
| `mmm_config.py` | `PARAM_RULES`: added type/min/max/hot rules for all 5 Split Ledger params. Description strings added for API info endpoint. |
| `mmm_activity.py` | Added `shift_recycle: 'Shift-Time Recycle'` to `ACTIVITY_TYPES`. Added to `adjustments` category in `ACTIVITY_CATEGORIES`. |

#### Profitability Suggestion 2: harvest_pressure_threshold

Lowered from 0.7 → 0.5 in `DEFAULT_PARAMS`. M1 harvesting now starts earlier (at 50% total capacity pressure instead of 70%), leading to steadier cleanup of frozen positions rather than emergency batches. Hot-reloadable — can be tuned in production.

---

### 2.20 ATM Shield — Proactive Close & Retreat (Implemented March 12, 2026)

**New File:** `mmm_atm_shield.py` (~450 lines)

Pre-emptively closes endangered-side positions when spot price approaches within `atm_shield_proximity_pct` (default 0.5%) of the active strike. This fires at **Step 5.5** in the heartbeat — between cooldown checks (Step 5) and trigger evaluation (Step 6) — so it acts BEFORE the standard adjustment logic.

**Core philosophy:** Unlike `close_at_ATM` (emergency stop), the ATM Shield is a *revenue-preserving retreat*. It closes the near-ATM position AND re-establishes it at a safer OTM strike, preserving premium collection capacity while protecting against gamma explosion.

#### How it Works

**Step 1 — Close:** Buy back ALL active positions on the endangered side.

**Step 2 — Find new strike:** Scan options chain for a strike at `atm_shield_target_otm_pct` (default 1.0%) OTM or farther. Widens progressively with each subsequent shield fire on that side.

**Step 3 — Re-sell (full position shift + loss recovery):**
- **Endangered side (exempt from trend Tier 1/2 lot reduction):**
  - `base_lots` = `total_closed_lots` (original lot count — full position shift, not just recovery)
  - `recovery_lots` = `ceil(buyback_loss × 0.30 / (new_premium × LOT_SIZE_BTC))`
  - Total re-sell = `base_lots + recovery_lots`, capped at `max_lots_per_side`
- **Safe side (normal regime rules apply):**
  - `recovery_lots` = `ceil(buyback_loss × 0.70 / (safe_premium × LOT_SIZE_BTC))`
  - Blocked by BLOCK_CE/PE_SELLS trend regime (only the endangered side is exempt)

**Example:** CE has 10 lots @ $100. Shield fires at premium $200.
- Buyback loss = ($200-$100) × 0.001 × 10 = $1.00
- New CE strike OTM, premium = $80
- CE re-sell: 10 (shifted) + ceil($0.30 / ($80×0.001)) = 10 + 4 = **14 lots**
- PE re-sell: ceil($0.70 / ($60×0.001)) = **12 lots** (recovery only)

**Step 4 — Sympathetic rebalance:** If safe-side premium has decayed below `shift_threshold`, immediately trigger a strike shift on the safe side.

#### Time Multiplier

As expiry approaches, the proximity threshold widens and the target OTM distance widens:
```
hours_to_expiry < 0.5h  →  time_mult = 3.0   (fires very early, retreats far)
hours_to_expiry = 1h    →  time_mult = 3.0
hours_to_expiry = 3h    →  time_mult = 1.0   (normal)
```

#### Gate Checks (must ALL pass to fire)
1. `atm_shield_enabled = True`
2. Session status = RUNNING
3. Margin tier not RED or CRITICAL
4. `minutes_to_expiry > auto_close_mins`
5. Cooldown: `>= atm_shield_cooldown_mins` since last fire on this side
6. Not exhausted: `shield_count < atm_shield_max_per_session`
7. Not already a proactive shift this beat

#### Regime Interaction
- In `_compute_regime_action()` (mmm_regime.py): when shield is enabled and has capacity, Trend Tier 1/2 returns `ACTION_NORMAL` instead of `ACTION_WARN`. Tier 3/4 still blocks all sells (vol/gamma blocking is always respected).
- In `calculate_lots_to_sell()` (mmm_engine.py): T1 lot-reduction block is bypassed when `atm_shield_enabled`.
- In `wind_down_on_atm` and `close_at_atm` blocks: if shield still has capacity, these defer and let the shield act instead.

#### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `atm_shield_enabled` | `false` | bool | Master on/off switch |
| `atm_shield_proximity_pct` | `0.5` | 0.1–5.0 | % distance from spot to strike that triggers fire |
| `atm_shield_target_otm_pct` | `1.0` | 0.1–10.0 | Target OTM % for new strike (progressive widening per fire) |
| `atm_shield_loss_split_aggressor` | `0.3` | 0.0–1.0 | Loss fraction recovered on endangered side (0.3 = 30%); remaining 70% recovered on safe side |
| `atm_shield_max_per_session` | `3` | 1–10 | Max shield fires per side per session |
| `atm_shield_cooldown_mins` | `10` | 0–60 | Minimum minutes between consecutive fires on same side |

All 6 parameters are **hot-reloadable**.

#### Session State Keys
| Key | Description |
|-----|-------------|
| `_atm_shield_count_ce` | CE fire count this session |
| `_atm_shield_count_pe` | PE fire count this session |
| `_atm_shield_last_fire_ce` | ISO timestamp of last CE fire |
| `_atm_shield_last_fire_pe` | ISO timestamp of last PE fire |
| `_atm_shield_exhausted_ce` | True when CE count >= max_per_session |
| `_atm_shield_exhausted_pe` | True when PE count >= max_per_session |
| `_atm_shield_fired` | Set True when shield fires this beat; popped by trigger-skip logic |

#### Files Modified
| File | Change |
|------|--------|
| `mmm_atm_shield.py` | **NEW** — core shield logic |
| `mmm_monitor.py` | Import + Step 5.5 block + `wind_down_on_atm`/`close_at_atm` deferral + trigger-skip |
| `mmm_regime.py` | Shield-aware override in `_compute_regime_action()` |
| `mmm_engine.py` | T1 lot-reduction bypass in `calculate_lots_to_sell()` |
| `mmm_strike_shift.py` | `min_otm_distance` parameter in `find_new_strike()` |
| `mmm_state.py` | 6 params in DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `mmm_config.py` | 6 PARAM_RULES entries |
| `mmm_activity.py` | `'atm_shield': 'ATM Shield'` activity type |
| `mmm_websocket.py` | `emit_atm_shield()` function |
| `MMMSettingsDialog.js` | ATM Shield settings group (pink, last group) |

**WebSocket event:** `mmm_atm_shield` — emitted on every shield fire with `{side, endangered_strike, spot_price, distance_pct, fire_number, fires_remaining, new_strike, realized_loss, lots_closed, lots_sold_endangered, lots_sold_safe, sympathetic_shifted}`.

**Activity type:** `atm_shield` — logged to activity ring buffer.

---

### 2.21 Breakeven Engine — Risk-Aware Lot Scaling (Implemented March 15, 2026)

**New File:** `mmm_breakeven_engine.py` (~605 lines)

Real-time portfolio breakeven awareness that increases hedge aggression when spot approaches the portfolio's profit/loss boundary. Computes the lower and upper BTC spot prices where total portfolio P&L = 0, classifies risk zones, and provides an aggression multiplier applied during lot calculation.

#### How It Works

**Phase 1: Compute Breakeven Prices (Position-Change Caching)**

Called at **Step 5.7** of the heartbeat loop (after ATM Shield, before trigger evaluation):

1. **Position collection** — Gather all open positions (active + frozen) from both CE and PE sides, including:
   - Original lots at active strike
   - Adjustment fills at active strike
   - Frozen positions at old strikes (from prior shifts)
   - Perp hedge position (if exists)

2. **Check cache** — Hash all position factors: (`strike`, `lots`, `entry_premium`) for each position + `realized_pnl` + perp (`lots`, `avg_entry`, `direction`). If hash matches cached hash, reuse cached breakeven prices (skip scan).

3. **Dynamic scan range** — If cache miss or positions changed:
   ```python
   furthest_strike_distance = max(abs(spot - p['strike']) for p in positions)
   min_range_from_strikes = furthest_strike_distance * 1.2  # 20% beyond furthest
   min_range_from_param = spot * (breakeven_scan_range_pct / 100)
   scan_range = max(min_range_from_strikes, min_range_from_param)
   ```
   Auto-expands to catch distant frozen positions from prior shifts.

4. **Intrinsic-only P&L model** at hypothetical spot `spot_h`:
   ```python
   for each short call at strike K, entry_premium P, lots N:
       intrinsic = max(spot_h - K, 0)
       pnl += (P - intrinsic) * N * 0.001

   for each short put at strike K, entry_premium P, lots N:
       intrinsic = max(K - spot_h, 0)
       pnl += (P - intrinsic) * N * 0.001

   pnl += realized_pnl  # vertical shift

   if perp hedge exists:
       signed_lots = perp_lots if direction == 'long' else -perp_lots
       pnl += (spot_h - perp_avg_entry) * signed_lots * 0.001
   ```
   **Conservative bias:** Ignores remaining extrinsic value → narrower breakeven band → earlier warnings. Correct direction for a risk tool.

5. **Breakeven scan** (coarse + binary search):
   - **Lower breakeven** (walk down from spot):
     - Coarse scan with ~80 sample points (step = spot × 0.002)
     - Detect sign change (P&L goes from positive to negative)
     - Binary search to converge within $10 precision (max 20 iterations)
   - **Upper breakeven** (walk up from spot):
     - Same coarse + binary search process
   - If no sign change found in scan range → return `None` (portfolio profitable in that direction)

6. **Cache result**:
   ```python
   cache[session_id] = {
       'lower_breakeven': lower,
       'upper_breakeven': upper,
       'positions_hash': hash,
       'band_width_pct': (upper - lower) / spot * 100,
       'computed_at': timestamp,
   }
   ```

**Performance:** Full scan+bisection ~1ms. Cached read ~0.01ms. Runs ~50-100x less frequently than every heartbeat.

---

**Phase 2: Distance & Zone Classification (Every Heartbeat)**

7. **Compute distances**:
   ```python
   if lower and lower < spot:
       distance_lower_pct = (spot - lower) / spot * 100
   if upper and upper > spot:
       distance_upper_pct = (upper - spot) / spot * 100

   nearest_distance_pct = min(distance_lower_pct, distance_upper_pct)
   nearest_side = 'lower' if distance_lower_pct < distance_upper_pct else 'upper'
   ```

8. **Classify zone**:
   ```python
   if nearest_distance_pct > breakeven_warning_pct:    zone = 'SAFE'
   elif nearest_distance_pct > breakeven_danger_pct:   zone = 'WARNING'
   elif nearest_distance_pct > breakeven_critical_pct: zone = 'DANGER'
   else:                                                zone = 'CRITICAL'
   ```

9. **Compute continuous multiplier** (linear interpolation prevents flip-flops):
   ```python
   if zone == 'SAFE':
       multiplier = 1.0

   elif zone == 'WARNING':
       progress = (warning_pct - nearest_distance_pct) / (warning_pct - danger_pct)
       multiplier = 1.0 + progress * 0.3  # 1.0 → 1.3

   elif zone == 'DANGER':
       progress = (danger_pct - nearest_distance_pct) / (danger_pct - critical_pct)
       multiplier = 1.3 + progress * 0.7  # 1.3 → 2.0

   elif zone == 'CRITICAL':
       progress = (critical_pct - nearest_distance_pct) / critical_pct
       multiplier = 2.0 + progress * (breakeven_aggression_max - 2.0)  # 2.0 → max
   ```

10. **Band diagnostics**:
    - **Band contraction** — Band width shrunk >30% since last position change → orange warning
    - **Narrow band** — Band width < `breakeven_narrow_band_threshold` (default 5% of spot) → yellow warning

11. **Store result on session**:
    ```python
    session['_breakeven_result'] = BreakevenResult dict (23 fields)
    session['_breakeven_multiplier'] = multiplier
    session['_breakeven_zone'] = zone
    ```

---

**Phase 3: Apply Multiplier in Lot Calculation**

In `mmm_engine.py` → `calculate_lots_to_sell()`, the multiplier is read from session at **Step 4** (after gamma-aware, before trend boost):

```python
# Step 3: Gamma-aware multiplier
gamma_mult = 1.0  # initialized before T3-2 block for combined ceiling scope
if gamma_aware_enabled and excess_pct > 10%:
    gamma_mult = 1.0 + min((excess_pct - 10) / 40, 0.3)  # 1.0–1.3×
    lots_to_sell *= gamma_mult

# Step 4: Breakeven multiplier (NEW)
breakeven_mult = session.get('_breakeven_multiplier', 1.0)
if breakeven_mult > 1.0:
    lots_to_sell = max(ceil(lots_to_sell * breakeven_mult), 1)

# Step 5: Trend boost/reduction
if trend_boost_active:
    lots_to_sell *= boost_mult  # 1.3–2.0×

# Step 5a: Combined multiplier ceiling (NEW)
max_combined = params.get('max_combined_lot_multiplier', 3.0)
combined = gamma_mult * breakeven_mult * (boost_mult if trend_boost_active else 1.0)
if combined > max_combined:
    overshoot = combined / max_combined
    lots_to_sell = max(ceil(lots_to_sell / overshoot), 1)
```

**Non-directional:** Multiplier applies to ALL triggered adjustments. Core trigger system already determines correct hedge direction (CE vs PE), so there's no need for directional filtering here.

**Stacking protection:** Combined ceiling prevents gamma(1.3) × breakeven(3.0) × trend(2.0) = 7.8× runaway. Caps compound product at `max_combined_lot_multiplier` (default 3.0×).

---

#### Cache Invalidation (Critical)

Cache must be invalidated after EVERY position-changing event so next heartbeat triggers a full scan+bisection:

| Event | Location | Invalidation Added |
|-------|----------|-------------------|
| Adjustment fill | `mmm_monitor.py` `_process_adjustment` | Line 3273 |
| Strike shift fill | `mmm_monitor.py` `_process_strike_shift` | Line 3863 |
| Shift fallback fill | `mmm_monitor.py` `_shift_fallback_sell` | Line 4031 |
| Close-at-5 fill | `mmm_monitor.py` `_process_close_at_5` | Line 4947 (audit fix) |
| M1 Harvest fill | `mmm_monitor.py` `_process_harvest` | Line 4139 (audit fix) |
| M2 Lot Recycle fill | `mmm_monitor.py` `_process_lot_recycling` | Line 4560 (audit fix) |
| Shift-time recycle | `mmm_monitor.py` `_shift_time_recycle` | Line 4744 (audit fix) |
| Operator inject | `mmm_api.py` `inject_position` | Line 3453 (audit fix) |

**Pattern:**
```python
try:
    get_breakeven_engine().invalidate_cache(session_id)
except Exception:
    pass
```

**Note:** Audit on March 15, 2026 found 5 missing invalidation calls (close-at-5, harvest, recycle, shift-time-recycle, inject). All fixed.

---

#### Parameters

| Parameter | Type | Default | Range | Hot | Description |
|-----------|------|---------|-------|-----|-------------|
| `breakeven_control_enabled` | bool | False | — | Yes | Master switch |
| `breakeven_warning_pct` | float | 2.0 | 0.5–10.0 | Yes | Distance % → WARNING zone (1.0–1.3× ramp) |
| `breakeven_danger_pct` | float | 1.0 | 0.2–5.0 | Yes | Distance % → DANGER zone (1.3–2.0× ramp) |
| `breakeven_critical_pct` | float | 0.5 | 0.1–2.0 | Yes | Distance % → CRITICAL zone (2.0–max ramp) |
| `breakeven_aggression_max` | float | 3.0 | 1.5–5.0 | Yes | Max multiplier at deepest CRITICAL zone |
| `breakeven_scan_range_pct` | float | 5.0 | 2.0–15.0 | Yes | Minimum scan width as % of spot |
| `max_combined_lot_multiplier` | float | 3.0 | 1.5–5.0 | Yes | Cap on gamma × breakeven × trend product |
| `breakeven_narrow_band_threshold` | float | 5.0 | 1.0–10.0 | Yes | Warn when band width < this % of spot |

**Interdependency validation:** `breakeven_critical_pct < breakeven_danger_pct < breakeven_warning_pct` (enforced in `mmm_config.py` `_interdependency_checks()`).

---

#### Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `_breakeven_result` | dict | Full BreakevenResult (23 fields) from last computation |
| `_breakeven_multiplier` | float | Aggression multiplier (1.0–max) for lot calculation |
| `_breakeven_zone` | str | Current zone: 'SAFE' / 'WARNING' / 'DANGER' / 'CRITICAL' |
| `_breakeven_zone_prev` | str | Previous zone (for transition detection) |

**BreakevenResult dict fields (23):**
- `enabled` (bool), `lower_breakeven` (float | None), `upper_breakeven` (float | None), `spot_price` (float)
- `distance_lower_pct` (float | None), `distance_upper_pct` (float | None)
- `nearest_distance_pct` (float | None), `nearest_side` (str: 'lower'/'upper'/'none')
- `zone` (str), `multiplier` (float), `pnl_at_spot` (float)
- `band_width_pct` (float | None), `band_width_prev_pct` (float | None), `band_contracting` (bool), `is_narrow_band` (bool)
- `computed_at` (ISO timestamp), `positions_included` (int), `perp_included` (bool), `from_cache` (bool)

---

#### Files Modified

| File | Change |
|------|--------|
| `mmm_breakeven_engine.py` | NEW — 605 lines, `BreakevenEngine` class with singleton pattern |
| `mmm_monitor.py` | Step 5.7: `compute_breakeven()` call, 8 `invalidate_cache()` calls |
| `mmm_engine.py` | Step 4: breakeven multiplier applied, Step 5a: combined ceiling |
| `mmm_state.py` | 8 new parameters in `DEFAULT_PARAMS` and `HOT_RELOAD_PARAMS` |
| `mmm_config.py` | `PARAM_RULES` entries, interdependency validation, param descriptions |
| `mmm_websocket.py` | `emit_breakeven()` function, embedded in `mmm_heartbeat` payload |
| `mmm_api.py` | GET `/api/mmm/session/<id>/breakeven` endpoint, inject invalidation |
| `mmm_activity.py` | 3 activity types: `breakeven_zone_change`, `breakeven_band_contracting`, `breakeven_narrow_band` |
| `MMMBreakevenPanel.js` | NEW — 317 lines, horizontal bar, zone colors, expanded table |
| `MMMSettingsDialog.js` | 8 parameters with tooltips in "Breakeven Engine" section |
| `MMMDashboard.js` | Panel import + conditional render |

**WebSocket events:**
- `mmm_breakeven` — standalone event with full BreakevenResult payload
- `mmm_heartbeat` — breakeven data embedded in `heartbeat.breakeven` field

**Activity types:** `breakeven_zone_change` (info/warning), `breakeven_band_contracting` (warning), `breakeven_narrow_band` (warning) — all categorized under 'safety'.

---

### 2.22 Gamma Detector Engine — Portfolio Curvature Boundaries (Implemented March 15, 2026)

**New File:** `mmm_gamma_detector.py` (~293 lines)

Companion to the Breakeven Engine. Identifies the nearest BTC spot prices where the portfolio's **loss rate begins to accelerate** — i.e., kink points in the piecewise-linear intrinsic P&L curve. These kinks occur at option strikes. Observation-only by default (zero trading impact until Phase 9 is enabled via `gamma_severity_multiplier_enabled=True`).

- **Breakeven Engine answers:** "Where does the portfolio start losing money?"
- **Gamma Detector answers:** "Where does the portfolio start losing money *faster*?"

#### How It Works

**Second-Difference Formula:**

```python
γ(s) = PnL(s − step) − 2 × PnL(s) + PnL(s + step)
```

Applied to the intrinsic-only piecewise-linear model, `γ(s)` is exactly **0** everywhere except at option strike prices (kink points). At a kink, `γ` spikes to a negative value:

```
spike = −(step_USD × N_lots × LOT_SIZE_BTC)
# e.g. 10 lots, $450 step: −(450 × 10 × 0.001) = −4.5 USD
```

**Boundary Scan (`_run_boundary_scan`):**

1. Walk **strictly below** current spot (i=1..scan_steps): compute second-diff at each step. First point where `γ < -epsilon` is the lower gamma boundary (nearest put kink).
2. Walk **strictly above** current spot (i=1..scan_steps): same logic for upper gamma boundary (nearest call kink).
3. `scan_steps=40`, `step=spot × (gamma_step_pct / 100)` (default 0.5%), `epsilon=0.3`.

**Important:** Scans start at i=1 (not i=0). Starting at i=0 would evaluate the current spot in both scans, causing both boundaries to be set to the same kink when spot is near a strike.

**Position-Change Caching:**

Same cache strategy as Breakeven Engine. Positions are hashed (`_hash_positions()`). If hash unchanged → reuse cached boundaries. Cache invalidated at the same 8 events as the Breakeven Engine.

**Zone Classification (Distance-Based):**

```python
nearest_distance_pct = min(lower_distance_pct, upper_distance_pct)
if nearest_distance_pct > gamma_warning_distance_pct:  zone = 'SAFE'
elif nearest_distance_pct > gamma_danger_distance_pct: zone = 'WARNING'
else:                                                   zone = 'DANGER'
```

No CRITICAL zone (3-tier: SAFE / WARNING / DANGER). Zone by distance to nearest boundary — NOT by severity score at current spot (which is always ~0 unless sitting directly on a strike).

**Severity Normalization:**

Raw second-diff value scales with portfolio size. Stored as a diagnostic field:
```python
severity = raw_second_diff / (total_lots × LOT_SIZE_BTC)
```
Portfolio-size-independent. Used for display/Phase 9 only, not for zone classification.

**Result stored at:** `session['_gamma_result']` (GammaResult dict, 19 fields).

---

#### GammaResult Dict (19 fields)

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | False if gamma_detector_enabled=False |
| `spot_price` | float | BTC spot at computation time |
| `lower_gamma_boundary` | float \| None | Nearest downside kink price |
| `upper_gamma_boundary` | float \| None | Nearest upside kink price |
| `gamma_severity_lower` | float \| None | Normalized severity at lower boundary |
| `gamma_severity_upper` | float \| None | Normalized severity at upper boundary |
| `gamma_zone` | str | 'SAFE' / 'WARNING' / 'DANGER' |
| `lower_distance_pct` | float \| None | % distance from spot to lower boundary |
| `upper_distance_pct` | float \| None | % distance from spot to upper boundary |
| `nearest_distance_pct` | float \| None | Minimum of lower/upper distance |
| `nearest_side` | str | 'lower' / 'upper' / 'none' |
| `from_cache` | bool | True if boundaries served from cache |
| `positions_included` | int | Number of positions scanned |
| `perp_included` | bool | True if perp hedge was in scan |
| `observation_only` | bool | True until gamma_severity_multiplier_enabled |
| `computed_at` | str | ISO timestamp |

---

#### Parameters

| Parameter | Type | Default | Range | Hot | Description |
|-----------|------|---------|-------|-----|-------------|
| `gamma_detector_enabled` | bool | False | — | Yes | Master switch |
| `gamma_step_pct` | float | 0.5 | 0.1–5.0 | Yes | Step size for scan as % of spot |
| `gamma_scan_steps` | int | 40 | 10–200 | Yes | Number of steps in each direction |
| `gamma_warning_distance_pct` | float | 3.0 | 0.1–20.0 | Yes | Distance % → WARNING zone |
| `gamma_danger_distance_pct` | float | 1.5 | 0.1–10.0 | Yes | Distance % → DANGER zone |
| `gamma_detect_epsilon` | float | 0.3 | 0.01–50.0 | Yes | Min |γ| to classify as a kink |
| `gamma_severity_multiplier_enabled` | bool | False | — | **No** | Phase 9 gate — enables trading impact |

**Note:** `gamma_severity_multiplier_enabled` is NOT hot-reloadable. Requires restart to enable. This prevents accidental live activation.

---

#### Cache Invalidation

All 8 invalidation calls are paired with Breakeven Engine invalidation at the same locations:

| Event | Location |
|-------|----------|
| Adjustment fill | `mmm_monitor.py` `_process_adjustment` |
| Strike shift fill | `mmm_monitor.py` `_process_strike_shift` |
| Shift fallback fill | `mmm_monitor.py` `_shift_fallback_sell` |
| Close-at-5 fill | `mmm_monitor.py` `_process_close_at_5` |
| M1 Harvest fill | `mmm_monitor.py` `_process_harvest` |
| M2 Lot Recycle fill | `mmm_monitor.py` `_process_lot_recycling` |
| Shift-time recycle | `mmm_monitor.py` `_shift_time_recycle` |
| Operator inject | `mmm_api.py` `inject_position` |

**Pattern:**
```python
get_breakeven_engine().invalidate_cache(session_id)
get_gamma_detector().invalidate_cache(session_id)
```

---

#### Heartbeat Integration

Called at **Step 5.8** of the heartbeat loop (immediately after Step 5.7 Breakeven Engine):

```python
gamma_result = get_gamma_detector().compute_gamma(session, spot_price, be_engine=be_engine)
session['_gamma_result'] = gamma_result
```

The `be_engine` instance is passed to avoid a second singleton lookup.

---

#### Files Modified

| File | Change |
|------|--------|
| `mmm_gamma_detector.py` | NEW — 293 lines, `GammaDetector` class with singleton pattern |
| `mmm_monitor.py` | Step 5.8: `compute_gamma()` call, 7 `invalidate_cache()` calls paired with breakeven |
| `mmm_state.py` | 7 new parameters in `DEFAULT_PARAMS`; 6 in `HOT_RELOAD_PARAMS` (not `gamma_severity_multiplier_enabled`) |
| `mmm_config.py` | 7 `PARAM_RULES` entries |
| `mmm_websocket.py` | `emit_gamma()` function, `gamma_data` param added to `emit_heartbeat()` |
| `mmm_api.py` | GET `/api/mmm/session/<id>/gamma` endpoint, inject invalidation paired |
| `mmm_activity.py` | 2 activity types: `gamma_zone_change`, `gamma_danger_detected` — categorized under 'safety' |
| `MMMGammaPanel.js` | NEW — collapsible panel, zone colors (SAFE/WARNING/DANGER), "Observation Only" chip |
| `MMMDashboard.js` | Panel import + conditional render (after MMMBreakevenPanel) |

**WebSocket events:**
- `mmm_gamma` — standalone event with full GammaResult payload
- `mmm_heartbeat` — gamma data embedded in `heartbeat.gamma` field

**Activity types:** `gamma_zone_change`, `gamma_danger_detected` — both categorized under 'safety'.

**Zero changes to `mmm_breakeven_engine.py`** — Python's single-underscore convention allows direct access to `_collect_open_positions()`, `_compute_pnl_at_spot()`, `_hash_positions()` without any modification to the sealed file.

---

## 3. ARCHITECTURE

### 3.1 File Structure (Complete — Verified March 12, 2026)

```
webui/
├── backend/
│   └── routes/
│       └── mmm/                              ← Isolated backend module
│           ├── __init__.py                   ← Blueprint registration, init_mmm()
│           ├── mmm_api.py                    ← REST API (~3398 lines, all endpoints)
│           ├── mmm_state.py                  ← State model, session creation (~839 lines)
│           ├── mmm_config.py                 ← Parameter validation, defaults (~438 lines)
│           ├── mmm_constants.py              ← Shared constants (LOT_SIZE_BTC = 0.001)
│           ├── mmm_storage.py                ← SQLite persistence (mmm_sessions.db, ~398 lines)
│           ├── mmm_websocket.py              ← 19 WebSocket event emitters (~490 lines, +emit_breakeven, +emit_gamma)
│           ├── mmm_initializer.py            ← Strike selection, chain data, expiries (~733 lines)
│           ├── mmm_executor.py               ← Smart execution, mid-price, reprice (~1199 lines)
│           ├── mmm_trigger.py                ← Trigger evaluation, theta acceleration (~348 lines)
│           ├── mmm_engine.py                 ← Core adjustment, P&L computation, Split Ledger cap (~763 lines)
│           ├── mmm_reversal.py               ← Reversal detection, cooldown, skip
│           ├── mmm_strike_shift.py           ← Freeze/find/activate strike shift (~342 lines)
│           ├── mmm_close_at_5.py             ← Position scanning, buyback, profit lock (~322 lines)
│           ├── mmm_safety.py                 ← All safety checks, trailing stop, total exposure (~739 lines)
│           ├── mmm_monitor.py                ← Background heartbeat loop thread, shift-time recycle (~5533 lines)
│           ├── mmm_wind_down.py              ← Wind-down mode logic (~348 lines)
│           ├── mmm_activity.py               ← Activity log ring buffer (~443 lines, added Feb 15, 2026)
│           ├── mmm_adopter.py                ← Adopt exchange positions into MMM (added Feb 18, 2026)
│           ├── mmm_analytics_aggregator.py   ← Institutional analytics from SQLite (added Feb 18, 2026)
│           ├── mmm_analytics_storage.py      ← Analytics data persistence
│           ├── mmm_circuit_breaker.py        ← 3-state API fault isolation (added Feb 18, 2026)
│           ├── mmm_heartbeat_health.py       ← Beat telemetry & A–F health grades (added Feb 18, 2026)
│           ├── mmm_margin_guardian.py        ← Real-time margin monitoring (added Feb 20, 2026)
│           ├── mmm_pending_orders.py         ← Duplicate order prevention (added Feb 18, 2026)
│           ├── mmm_regime.py                 ← Regime-aware risk controls (added Feb 20, 2026)
│           ├── mmm_telegram.py               ← Telegram alert notifications (added Feb 20, 2026)
│           ├── mmm_walkthrough.py            ← Algo walkthrough generator (added Feb 16, 2026)
│           ├── mmm_watchdog.py               ← Monitor watchdog/auto-restart (added Feb 18, 2026)
│           ├── mmm_perp_hedge.py             ← Perpetual futures delta hedge (added Feb 22, 2026, ~441 lines)
│           ├── mmm_harvester.py              ← M1 Profit Harvesting + M3 Asymmetry scanner (~246 lines, added Mar 3, 2026)
│           ├── mmm_recycler.py               ← M2 Lot Recycling two-phase execution (~514 lines, added Mar 3, 2026)
│           ├── mmm_atm_shield.py             ← ATM Shield proactive close & retreat (~450 lines, added Mar 12, 2026)
│           ├── mmm_breakeven_engine.py       ← Breakeven scan + risk-aware lot scaling (~605 lines, added Mar 15, 2026)
│           ├── mmm_gamma_detector.py         ← Gamma boundary scan, curvature detection (~293 lines, added Mar 15, 2026)
│           ├── mmm_dte_presets.py             ← Multi-DTE presets, aggregate PnL safety, liquidity gate (~306 lines, added Mar 12, 2026)
│           ├── mmm_sessions.db               ← SQLite session data (replaces mmm_sessions.json)
│           └── tests/                        ← Unit tests (13 files)
│
├── frontend/
│   └── src/
│       └── components/
│           └── mmm/                          ← Isolated frontend module
│               ├── index.js                  ← Barrel exports
│               ├── MMMDashboard.js           ← Main dashboard container
│               ├── MMMConfigPanel.js         ← 3-mode config: Fresh/Manual/Import
│               ├── MMMStrikeSelector.js      ← Manual strike browser from chain
│               ├── MMMContext.js             ← React Context + WebSocket listeners
│               ├── MMMErrorBoundary.js       ← Error boundary wrapper
│               ├── mmmService.js             ← API service client (axios)
│               ├── MMMStatusBanner.js        ← Running/Paused/Stopped status bar
│               ├── MMMPositionsTable.js      ← Active + frozen positions table
│               ├── MMMTriggerGauge.js        ← Visual trigger gauges per side
│               ├── MMMAdjustmentLog.js       ← Adjustment history timeline
│               ├── MMMSessionCard.js         ← Session card with controls
│               ├── MMMStrikeMap.js           ← Strike visualization
│               ├── MMMPnLChart.js            ← P&L chart (Recharts)
│               ├── MMMBothSidesAlert.js      ← Both-sides decision modal
│               ├── MMMSafetyPanel.js         ← Safety dashboard (8 indicators)
│               ├── MMMConsolidatedPositions.js ← Grouped fills by (side, strike)
│               ├── MMMGreeksPanel.js         ← Live Greeks & IV panel
│               ├── MMMActivityFeed.js        ← Real-time background activity log
│               ├── MMMAdoptPanel.js          ← Adopt existing exchange positions UI
│               ├── MMMAlgoCalculations.js    ← Walkthrough calculation display
│               ├── MMMAnalyticsPanel.js      ← Institutional analytics dashboard
│               ├── MMMAnalyticsSummary.js    ← Analytics summary cards
│               ├── MMMAnalyticsTable.js      ← Analytics session history table
│               ├── MMMEducation.js           ← Educational tooltips and guides
│               ├── MMMMarginGuardianPanel.js ← Margin utilization & tier display
│               ├── MMMRegimePanel.js         ← Regime status (vol/gamma/trend)
│               ├── MMMPerpHedgePanel.js      ← Perpetual futures delta hedge UI (added Feb 22, 2026)
│               ├── MMMBreakevenPanel.js      ← Breakeven boundary display, zone colors, band metrics (added Mar 15, 2026)
│               ├── MMMGammaPanel.js          ← Gamma boundary display, observation-only (added Mar 15, 2026)
│               ├── MMMSettingsDialog.js      ← Hot-reload params dialog, Split Ledger settings (~669 lines)
│               ├── hooks/
│               │   ├── useMMMParams.js       ← Parameter dirty tracking
│               │   └── useMMMWebSocket.js    ← WebSocket subscription hook
│               └── utils/
│                   ├── mmmFormatters.js      ← Number/time/strike formatters
│                   └── mmmCalculations.js    ← Client-side P&L math
```

### 3.2 Integration Points (Only 2 Existing Files Modified)

| File | Change |
|------|--------|
| `webui/backend/app.py` | Lines 476-487: `register_blueprint(mmm_bp)` + `init_mmm()` in try/except |
| `webui/frontend/src/App.js` | Line 67: import `MMMErrorBoundary, MMMProvider`; Line 147: lazy import `MMMDashboard`; Line 594: MMM tab; Lines 1522-1530: `<MMMProvider socket={socket}>` wrapping `<MMMDashboard />` |

### 3.3 Runtime Architecture

```
Flask Backend (port 5555)
├── Blueprint: /api/mmm/*
├── MMMMonitor: background thread per session (heartbeat loop)
├── MMMWatchdog: supervisor thread that auto-restarts dead monitors
├── MMMStorage: SQLite persistence (data/mmm_sessions.db)
│   └── Auto-migrates legacy data/mmm_sessions.json on first run
├── CircuitBreaker: per-session API fault isolation
├── MarginGuardian: per-session real-time margin monitoring
├── SocketIO: emits mmm_* events to frontend
└── LaunchAgent: com.gridbot.webui (auto-restart)

React Frontend (production build served by Flask)
├── MMMProvider: wraps MMMDashboard, receives socket prop from App.js
├── MMMContext: manages sessions, WebSocket listeners, state
├── MMMDashboard: session list + detail view with multiple tabs
└── CreateSessionDialog: mode selection (Fresh/Import/Adopt), expiry, params
```

### 3.4 Key Constants

```python
# mmm_constants.py
LOT_SIZE_BTC = 0.001  # 1 BTC option lot = 0.001 BTC on Delta Exchange
                       # USD value for N lots = premium_per_btc × N × LOT_SIZE_BTC
```

---

## 4. API REFERENCE

### 4.1 Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/health` | Health check |
| `GET` | `/api/mmm/sessions` | List all sessions |
| `GET` | `/api/mmm/session/<id>` | Get full session details |
| `POST` | `/api/mmm/session/create` | Create session (mode: fresh/import/adopt) |
| `DELETE` | `/api/mmm/session/<id>` | Delete (IDLE/STOPPED only) |

### 4.2 Initialization

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/expiries` | Available BTC expiry dates (DDMMYYYY format) |
| `GET` | `/api/mmm/spot-price` | Current BTC spot price |
| `POST` | `/api/mmm/preview-strikes` | Preview strikes for desired premiums |
| `POST` | `/api/mmm/session/<id>/init-fresh` | Initialize with confirmed strikes |
| `POST` | `/api/mmm/session/<id>/init-import` | Initialize from existing positions |
| `POST` | `/api/mmm/check-liquidity` | Bid-side liquidity check |
| `GET` | `/api/mmm/chain-data` | Full options chain for manual selection |
| `POST` | `/api/mmm/validate-selection` | Validate a manually selected strike |
| `POST` | `/api/mmm/session/<id>/execute-entry` | Smart execution at mid-price |

### 4.3 Adopt Mode

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/exchange-positions` | Fetch open short BTC options from Delta Exchange |
| `POST` | `/api/mmm/session/<id>/adopt` | Map exchange positions into session state |

### 4.4 Session Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/start` | Start monitoring |
| `POST` | `/api/mmm/session/<id>/pause` | Pause monitoring |
| `POST` | `/api/mmm/session/<id>/resume` | Resume monitoring |
| `POST` | `/api/mmm/session/<id>/stop` | Stop session |
| `POST` | `/api/mmm/session/<id>/force-heartbeat` | Trigger an immediate heartbeat |
| `POST` | `/api/mmm/session/<id>/reduce-position` | User-initiated position reduction |

### 4.5 Real-Time Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/state` | Full session state snapshot |
| `GET` | `/api/mmm/session/<id>/positions` | All positions (active + frozen) |
| `GET` | `/api/mmm/session/<id>/history` | Adjustment history |
| `GET` | `/api/mmm/session/<id>/pnl-timeline` | P&L over time |
| `GET` | `/api/mmm/session/<id>/triggers` | Current trigger values |
| `GET` | `/api/mmm/session/<id>/safety` | Safety status |
| `GET` | `/api/mmm/session/<id>/regime` | Regime status (vol/gamma/trend) |
| `GET` | `/api/mmm/session/<id>/greeks-iv` | Live Greeks, IV, mark price for all positions |
| `GET` | `/api/mmm/session/<id>/walkthrough` | Algo calculation walkthrough log |
| `GET` | `/api/mmm/session/<id>/beat-health` | Heartbeat health (latency percentiles, A–F grade) |
| `GET` | `/api/mmm/session/<id>/margin` | Session margin utilization from exchange |
| `GET` | `/api/mmm/session/<id>/monitor` | Monitor thread status |
| `GET` | `/api/mmm/monitors` | Status of all active monitors |

### 4.6 Parameters

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/params/info` | Descriptions for all parameters (for tooltips) |
| `GET` | `/api/mmm/session/<id>/params` | Get current parameters |
| `PATCH` | `/api/mmm/session/<id>/params` | Update hot-reload params |

### 4.7 User Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/both_sides_decision` | Handle both-sides-up decision |
| `POST` | `/api/mmm/session/<id>/close-all` | Close all positions immediately |

### 4.8 Exchange Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/exchange/margin` | Raw exchange margin data |
| `GET` | `/api/mmm/exchange/positions` | All open exchange positions |
| `GET` | `/api/mmm/exchange/orders` | All open exchange orders |

### 4.9 Activity Log

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/activities` | Recent background activity entries (ring buffer, max 200) |

### 4.10 Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/analytics` | Per-session analytics |
| `GET` | `/api/mmm/analytics/history` | Analytics history (all sessions) |
| `GET` | `/api/mmm/analytics/aggregated` | Aggregated institutional analytics |

### 4.11 Perpetual Futures Delta Hedge

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/hedge/status` | Current perp hedge state (delta, lots, direction, P&L) |
| `POST` | `/api/mmm/session/<id>/hedge/toggle` | Enable/disable perp hedge |
| `POST` | `/api/mmm/session/<id>/hedge/close` | Close perp hedge position immediately |

### 4.12 Multi-DTE / Aggregate Safety

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/dte-presets` | Available DTE presets with full parameter details |
| `GET` | `/api/mmm/aggregate-pnl` | Combined P&L across all active sessions with safety level |

### 4.13 WebSocket Events (22 total)

| Event | When | Key Payload Fields |
|-------|------|-------------------|
| `mmm_heartbeat` | Every interval | session_id, ce_premium, pe_premium, triggers, status, adaptive_tier, wind_down_active |
| `mmm_price_tick` | Per-price update | session_id, premium_map |
| `mmm_adjustment` | On adjustment | session_id, side, lots, premium, strike, loss_covered, type |
| `mmm_reversal` | On reversal | session_id, from_side, to_side, adj_pnl, action |
| `mmm_shift` | On strike shift | session_id, side, old_strike, new_strike, frozen_lots |
| `mmm_close_at_5` | On close-at-5 | session_id, side, strike, lots, realized_pnl |
| `mmm_both_sides` | Both sides up | session_id, ce_details, pe_details |
| `mmm_safety` | Safety event | session_id, type, level, message |
| `mmm_pnl_update` | Every interval | session_id, total, realized, unrealized, fees |
| `mmm_params_changed` | On hot-reload | session_id, changed_params |
| `mmm_session_created` | New session | session_id, summary |
| `mmm_session_deleted` | Session deleted | session_id |
| `mmm_status_change` | Status change | session_id, old_status, new_status |
| `mmm_activity` | New activity log entry | activity dict (type, message, session_id, timestamp) |
| `mmm_activities_updated` | Activity log refresh | refresh: true |
| `mmm_regime` | Regime status update | session_id, regime_status (vol/gamma/trend/aggregate) |
| `mmm_harvest` | On profit harvest | session_id, side, strike, lots, profit_pct, realized_pnl |
| `mmm_recycle` | On lot recycling | session_id, side, recycled_lots, new_lots, new_strike, net_lot_gain |
| `mmm_perp_hedge_update` | Every heartbeat (when enabled) | session_id, effective_delta, hedge_lots, direction, unrealized_pnl |
| `mmm_perp_hedge_execution` | On perp trade placed | session_id, action (open/rebalance/close), lots, price, side |
| `mmm_perp_hedge_flip` | On direction flip (long↔short) | session_id, old_direction, new_direction, lots |

---

## 5. STATE MODEL

### 5.1 Per-Side State (CE and PE each)

```python
{
    'original_lots': int,           # Lots sold at entry
    'original_premium': float,      # Premium per lot at entry
    'original_strike': float,       # Strike at entry
    'active_strike': float,         # Current monitoring strike (changes on shift)
    'adjustment_fills': [           # Fills at ACTIVE strike
        {'lots': int, 'premium': float, 'strike': float, 'timestamp': str}
    ],
    'adjustment_total_lots': int,   # Sum of lots in adjustment_fills
    'adjustment_avg': float,        # Weighted avg premium of adj fills
    'frozen_positions': [           # Old positions after strike shift
        {'strike': float, 'lots': int, 'entry_premium': float}
    ],
    'frozen_total_lots': int,       # Sum of frozen lots
    'active_lots': int,             # original_lots + adjustment_total_lots
    'total_lots': int,              # active_lots + frozen_total_lots
    'trigger_snapshot': {           # {strike: premium_at_last_update}
        'strike_value': float
    }
}
```

### 5.2 Global State

```python
{
    'session_id': str,              # UUID
    'strategy_status': str,         # IDLE → RUNNING → PAUSED/BOTH_SIDES_UP → STOPPED
    'last_aggressor': str,          # 'CE' | 'PE' | 'NONE'
    'adjustment_count': int,
    'reversal_count': int,
    'shift_count': int,
    'close_at_5_count': int,
    'adjustment_history': [],       # Ordered list of all adjustments
    'realized_pnl': float,         # From close-at-5 events
    'unrealized_pnl': float,       # Current mark-to-market
    'total_premium_collected': float,
    'total_fees': float,
    'peak_pnl': float,             # High-water mark for trailing stop
    'cooldown_active': bool,
    'created_at': str,              # ISO timestamp
    'entry_time': str,              # When initialized
    'params': {},                   # All configurable parameters
    '_atm_wind_down_triggered': bool,  # Set once when ATM wind-down fires; persists session
    '_watchdog_restarts': int,      # Count of monitor auto-restarts by watchdog
    'harvest_count': int,           # M1: Total successful profit harvests
    'harvest_lots_freed': int,      # M1: Cumulative lots freed by harvesting
    'recycle_count': int,           # M2: Total SUCCESSFUL lot recycles
    'recycle_attempt_count': int,   # M2: Total recycle attempts (includes failures)
    '_last_recycle_at': str,        # ISO timestamp of last recycle (for cooldown)
    'perp_hedge': {                 # Perpetual futures delta hedge state
        'enabled': bool,            # Whether perp hedge is active
        'direction': str,           # 'LONG' | 'SHORT' | 'FLAT'
        'lots': int,                # Current perp position lots
        'entry_price': float,       # Average entry price
        'effective_delta': float,   # Current portfolio delta
        'unrealized_pnl': float,    # Mark-to-market P&L on perp
        'realized_pnl': float,      # Closed P&L from perp trades
        'last_rebalance': str,      # ISO timestamp of last rebalance
        'trade_count': int,         # Total perp trades this session
        'cooldown_until': str,      # ISO timestamp when cooldown expires
    },
    'shift_recycle_stats': {         # ROI tracking for shift-time recycle (Suggestion 3)
        'total_buyback': float,     # Cumulative buyback cost in USD
        'total_lots_freed': int,    # Cumulative lots freed by shift-time recycle
        'total_shifts': int,        # Count of shifts where recycle fired
    },
}
```

---

## 6. BACKEND MODULE DETAILS

### 6.1 mmm_state.py (~839 lines)
- `create_session(mode, params)` → creates session dict with all state fields
  - If `dte_category` is set in params, applies DTE preset via `apply_preset()` from `mmm_dte_presets.py`
  - Computes `total_dte_hours` from expiry via `compute_total_dte_hours()` and stores in params
- `initialize_side_from_entry(session, side, strike, premium, lots)` → sets per-side state
- `get_session_summary(session)` → compact summary for WebSocket/API (includes `dte_category`)
- `DEFAULT_PARAMS` includes all Split Ledger params + DTE params: `dte_category`, `total_dte_hours`, `global_max_loss`
- `HOT_RELOAD_PARAMS` includes `global_max_loss`

### 6.2 mmm_config.py (~443 lines)
- `PARAM_RULES` dict with all 30+ parameters (including adaptive + wind-down + Split Ledger + DTE)
- Split Ledger PARAM_RULES: `max_total_exposure`, `shift_recycle_enabled`, `shift_recycle_premium_floor`, `shift_recycle_max_pct`, `shift_recycle_floor_ratio`
- DTE PARAM_RULES: `dte_category` (str, not hot), `total_dte_hours` (float [0, 10000], not hot), `global_max_loss` (float [100, 1e9], hot)
- `validate_params(user_params)` → validates types, ranges, returns (validated, errors)
- `get_param_info()` → returns descriptions for all params for WebUI tooltips

### 6.3 mmm_constants.py
- `LOT_SIZE_BTC = 0.001` — Delta Exchange BTC options: 1 lot = 0.001 BTC
- Imported by: `mmm_engine.py`, `mmm_adopter.py`, `mmm_walkthrough.py`, `mmm_regime.py`
- Used wherever premiums need to be converted to USD notional values

### 6.4 mmm_storage.py (~398 lines)
- `MMMStorage` class — **SQLite persistence** (migrated from JSON on Feb 17, 2026)
- DB file: `data/mmm_sessions.db`
- Schema: `mmm_sessions(session_id TEXT PRIMARY KEY, params_json TEXT, data_json TEXT)`
- `params_json` stores params separately for atomic hot-reload
- On first init, auto-migrates `data/mmm_sessions.json` → renamed to `.json.migrated`
- Methods: `save_session`, `get_session`, `get_all_sessions`, `delete_session`

### 6.5 mmm_api.py (~3398 lines)
- Flask Blueprint at `/api/mmm`
- All REST endpoints (see Section 4)
- Uses lazy-loaded singletons: `get_storage()`, `get_initializer()`, `get_monitor()`

### 6.6 mmm_initializer.py (~733 lines)
- `MMMInitializer` class
- `auto_find_strikes(desired_ce, desired_pe, expiry)` → scans chain, finds best strikes
- `preview_strikes(...)` → returns found + alternatives without executing
- `get_available_expiries(underlying)` → delegates to OptionsChainService
- `get_spot_price(underlying)` → current BTC price
- `get_full_chain(expiry)` → complete options chain for manual selection
- Uses `OptionsChainService` (lazy loaded, sync, no auth needed)

### 6.7 mmm_executor.py (~1199 lines)
- `MMMExecutor` class — smart order execution
- Mid-price placement with 60-second fill wait
- Auto-reprice cycle if not filled
- Handles both entry orders and adjustment orders

### 6.8 mmm_trigger.py (~530 lines)
- `evaluate_triggers(session, ce_now, pe_now)` → returns which sides triggered
- Percentage-based `min_trigger_move_pct` filter (3% of trigger level)
- `compute_adaptive_interval()` → dynamic interval based on hours-to-expiry (v1: absolute thresholds for 0DTE)
- `compute_adaptive_interval_v2()` → percentage-of-DTE tiers for multi-DTE (>80%→1.5×, 50-80%→1.0×, 20-50%→0.7×, 5-20%→0.5×, <5%→0.3×)
- `apply_theta_acceleration()` → near-expiry trigger widening (v1: absolute 30-min window)
- `apply_theta_acceleration_v2()` → DTE-scaled window (2% of total DTE, capped at 240 min)
- Theta acceleration: widens triggers near expiry

### 6.9 mmm_engine.py (~763 lines)
- `MMMEngine.calculate_adjustment(session, aggressor, ce_now, pe_now)` → loss, lots, strike
- Standard loss formula: `active_loss + shifted_loss` (ALL positions included, Section 5 Case A)
- First-reversal P&L per-fill (Section 5 Case B)
- Lots calculation with ceiling, buffer, constraints
- `calculate_standard_loss()` accepts optional `fetch_premium_fn` to get live premiums for shifted positions
- **Split Ledger:** Position cap checks `active_lots` (not `total_lots`). "Position cap reached" message triggers M2 recycler
- **max_total_exposure ceiling:** Separate check after cap — clips lots if `active + frozen` would exceed ceiling. Uses distinct "Total exposure ceiling" message (intentionally differs from cap message to avoid false M2 triggers)

### 6.10 mmm_reversal.py
- `detect_reversal(session, current_aggressor)` → bool
- `compute_adjustment_pnl(session, side)` → float (positive=profitable, negative=underwater)
- Cooldown logic — skip 1 interval

### 6.11 mmm_strike_shift.py (~342 lines)
- `check_shift_needed(session, side, current_premium)` → bool
- `find_new_strike(session, side, expiry)` → strike info
- `execute_shift(session, side, new_strike)` → freezes old, activates new

### 6.12 mmm_close_at_5.py (~322 lines)
- `scan_closeable_positions(session, prices)` → list of positions at ≤ threshold
- `close_position(session, position)` → records realized P&L
- Handles side fully closed, both sides closed

### 6.13 mmm_safety.py (~850 lines)
- `MMMSafety` class with all 9+ safety checks
- Methods: `check_position_cap`, `check_total_exposure`, `check_max_adjustments`, `check_max_loss`, `check_whipsaw`, `check_asymmetry`, `check_near_expiry`, `check_near_expiry_v2`, `check_trailing_profit`, `check_pnl_guardrail`
- **`check_near_expiry_v2()`:** DTE-aware near-expiry for multi-DTE sessions. Three tiers: (1) absolute auto-close/stop-adjustment (same as v1), (2) wind-down zone from preset's `wind_down_hours_before_expiry`, (3) percentage-based early warning (last 5% of total DTE)
- **Dispatch:** `run_all_checks()` auto-dispatches v2 when `total_dte_hours > 36` and `dte_category != '0DTE'`
- **Split Ledger:** `check_position_cap` uses `active_lots` (not `total_lots`)
- **`check_total_exposure()`:** Warning-only check on `active + frozen` vs `max_total_exposure`. Action='warn' (does not block). Asymmetry check uses `total_lots` (unchanged)
- **`check_whipsaw()` (Mar 2026 rewrite):** Adaptive Whipsaw Guard — score-based graduated response (NORMAL/CAUTION/RESTRICT/COOLDOWN). Auto-migrates old binary pause state on first call. See T3-3 in §15.

### 6.14 mmm_monitor.py (~5533 lines)
- `MMMMonitor` class — runs heartbeat in background thread per session
- `start_session_monitor(session_id)`, `stop_session_monitor(session_id)`
- `pause_session(session_id)`, `resume_session(session_id)`
- Each heartbeat: fetch prices (circuit breaker) → close-at-5 → wind-down check → regime check → margin guardian → safety → pending order guard → triggers → adjust → walkthrough log → activity log → WebSocket emit
- Adaptive interval: selects next interval based on `compute_adaptive_interval()` (v1) or `compute_adaptive_interval_v2()` (multi-DTE)
- **Multi-DTE dispatch (~lines 620-660):** If `total_dte_hours > 36` AND `dte_category != '0DTE'`, uses v2 functions for adaptive interval and theta acceleration; otherwise uses v1
- Wind-down integration: calls `_process_wind_down_buyback()` before normal adjustment logic
- Prefetches all premiums in parallel for multi-strike sessions
- **Shift-Time Recycle:** `_shift_time_recycle()` method (~lines 3392-3534) hooks into strike-shift flow. Scans frozen positions at old strike, applies dynamic premium floor (`shift_recycle_floor_ratio`), caps at `shift_recycle_max_pct`, folds buyback cost into `total_loss_to_cover`. ROI tracked in `session['shift_recycle_stats']`
- **Orphan Adoption Fix (Mar 2026):** `_reconcile_exchange_positions()` now uses exchange `entry_price` as `entry_premium` for adopted orphan positions (previously hardcoded to 0, breaking loss calculations). Self-heal block scans existing active positions with `entry_premium=0` and patches them from exchange data each reconciliation cycle.
- **Whipsaw Guard Integration (Mar 2026):** Applies trigger multiplier (1.5× CAUTION, 2.0× RESTRICT) before `evaluate_triggers()` and lot reduction (50% at RESTRICT+) after `calculate_lots_to_sell()`. Records `spot` in `adjustment_history`.

### 6.15 mmm_wind_down.py (~348 lines)
- `is_wind_down_active(session, minutes_to_expiry)` → bool
- `compute_wind_down_action(session, premiums, minutes_to_expiry)` → action dict
- `get_lifo_close_fills(session, side)` → positions in LIFO order for closing
- `apply_lifo_removals(session, side, fills)` → removes closed positions from state
- `get_wind_down_close_threshold(entry_premium, params)` → elevated threshold

### 6.16 mmm_websocket.py (~240 lines)
- 17 event emitter functions (see Section 4.11 for full list)
- Key emitters: `emit_heartbeat`, `emit_price_tick`, `emit_adjustment`, `emit_reversal`, `emit_strike_shift`, `emit_close_at_5`, `emit_both_sides_alert`, `emit_safety`, `emit_pnl_update`, `emit_params_changed`, `emit_session_created`, `emit_session_deleted`, `emit_status_change`, `emit_activity`, `emit_activities_updated`, `emit_regime`
- Heartbeat payload includes `adaptive_tier` and `wind_down_active` fields
- Uses Flask-SocketIO (same instance as main app)

### 6.17 __init__.py
- Exports `mmm_bp` (Blueprint) and `init_mmm()` (startup restoration)
- `init_mmm()`: checks for sessions with status=RUNNING, restores their monitors, starts MMMWatchdog supervisor thread

### 6.18 mmm_activity.py (Added Feb 15, 2026, ~443 lines)
- In-memory + persisted ring buffer of background activity events (max 200)
- Persisted to `data/mmm_activity_log.json`
- Captures: order lifecycle (placing/filled/repricing/failed), entry, session lifecycle, heartbeat execution, adjustments, reversals, safety events
- `ACTIVITY_TYPES` dict defines all event type labels including `shift_recycle: 'Shift-Time Recycle'`
- `shift_recycle` categorized under `adjustments` category
- Used by `MMMActivityFeed.js` frontend to show real-time "what is the algo doing" feed

### 6.19 mmm_adopter.py (Added Feb 18, 2026, ~561 lines)
- `fetch_exchange_btc_options(expiry_filter)` → fetches open short BTC options from Delta Exchange
- `classify_positions(selected, session)` → maps selected positions to active/frozen per side
- `validate_adoptable(positions)` → sanity-checks before committing
- `build_adopted_session_state(...)` → produces full session state dict
- Uses `DeltaClient` (lazy loaded). Zero changes to runtime modules.
- Adopted sessions behave identically to import sessions once state is built

### 6.20 mmm_analytics_aggregator.py (Added Feb 18, 2026, ~763 lines)
- Answers three core questions from REAL historical SQLite data:
  1. Capital planning: margin reserve needed to scale to N lots/side
  2. Risk profiling: auto-close/max-loss frequency, worst-case drawdown
  3. Strategy validation: win rate, profit factor, expected value per session
- All numbers from real data — nothing simulated

### 6.21 mmm_analytics_storage.py
- Persists per-session analytics snapshots for historical analysis
- Used by `mmm_analytics_aggregator.py` and analytics API endpoints

### 6.22 mmm_circuit_breaker.py (Added Feb 18, 2026)
- `CircuitBreaker` class — three states: `CLOSED`, `OPEN`, `HALF_OPEN`
- `FAILURE_THRESHOLD = 3`, `RESET_TIMEOUT = 30.0s`
- `CONSECUTIVE_OPEN_ALERT_THRESHOLD = 3` (emits safety event after 3 successive probe failures)
- Graduated response: partial beat (close-at-5 only) on early backoff; full skip on backoff 4+
- Never terminates the session — always self-healing

### 6.23 mmm_heartbeat_health.py (Added Feb 18, 2026, ~366 lines)
- `HeartbeatHealth` class — attached to each `MMMMonitor` instance (pure observability)
- `BeatRecord` dataclass: timestamp, latency_ms, outcome (`ok`/`partial`/`miss`/`error`), premiums
- Rolling windows: 100 beats for latency percentiles, 50 for miss rate, 10 for failure count
- Health Grade A–F: A=p95 < 80% interval + miss_rate < 2% + no failures in last 10
- `seconds_since_last_beat` used by watchdog to detect stuck threads
- Accessible via `GET /api/mmm/session/<id>/beat-health`

### 6.24 mmm_margin_guardian.py (Added Feb 20, 2026, ~478 lines)
- `MarginGuardian` class — queries Delta Exchange for actual margin utilization
- 5 tiers: GREEN, YELLOW, ORANGE, RED, CRITICAL (user-configurable thresholds)
- `tier_severity(tier)` → numeric severity (0=GREEN, 4=CRITICAL)
- Triggers wind-down on ORANGE, emergency close on RED, session stop on CRITICAL
- Sends Telegram alerts on tier escalation via `mmm_telegram.py`

### 6.25 mmm_pending_orders.py (Added Feb 18, 2026)
- In-memory `_registry` of in-flight orders per session per side (thread-safe)
- Prevents duplicate adjustment orders when `smart_execute` times out
- On each adjustment: verifies state (filled/open/dead) → decides allow/skip/record
- Orders stale after `_STALE_SECONDS = 900` (15 minutes)
- Filled states: `filled`, `closed`, `completed` — Dead states: `cancelled`, `rejected`, `expired`

### 6.26 mmm_regime.py (Added Feb 20, 2026, updated with Tiered Trend Guard)
- `RegimeEngine` class — no I/O; receives data, returns decisions
- Three controls: Volatility Regime Filter, Portfolio Gamma Cap, Trend Detection Guard (4-tier)
- Vol states: `NORMAL`, `ELEVATED`, `HIGH` — Gamma states: `NORMAL`, `SOFT`, `HARD`, `EMERGENCY`
- Trend tiers: `TIER_NONE(0)`, `TIER_ALERT(1)`, `TIER_GUARD(2)`, `TIER_BLOCK(3)`, `TIER_WIND_DOWN(4)`
- Legacy trend states still set for backward compat: `NORMAL`, `TREND_UP`, `TREND_DOWN`
- Aggregate actions: `ACTION_NORMAL`, `ACTION_WARN`, `ACTION_BLOCK_CE/PE_SELLS`, `ACTION_BLOCK_ALL_SELLS`, `ACTION_FORCE_REDUCE`
- Key functions: `_check_acceleration()`, `_compute_trend_tier()`, `_update_trend_guard()`
- Called by monitor heartbeat between safety checks and trigger evaluation

### 6.27 mmm_telegram.py (Added Feb 20, 2026)
- Sends Telegram notifications for critical margin/safety events
- Uses existing async `TelegramNotifier` infrastructure
- Dedup window: `_DEDUP_WINDOW_SECS = 30` (no repeat alerts within 30s)
- Credentials from `config.loader.get_config().telegram.*` (live_bot_token, live_chat_id)
- Disabled by default — requires valid Telegram bot token + chat ID

### 6.28 mmm_walkthrough.py (Added Feb 16, 2026, ~907 lines as of Feb 2026 enhancement)
- `generate_entry_walkthrough(session)` → T=0 entry block in human-readable format
- `generate_heartbeat_walkthrough(session, ce_now, pe_now, ..., regime_info=None, margin_info=None, perp_hedge_info=None)` → per-heartbeat log step
  - Signature backward-compatible; new kwargs default to `None`
  - `regime_info`: dict from `mmm_monitor._hb_wt['regime']` — contains `action`, `vol_regime`, `gamma_regime`, `trend_tier`, `trend_move_pct`, `observation_mode`, etc.
  - `margin_info`: dict from `mmm_monitor._hb_wt['margin']` — contains `tier`, `utilization_pct`, `blocked`, `wind_down`, `net_equity`, `position_margin`
  - `perp_hedge_info`: dict from `mmm_monitor._hb_wt['perp_hedge']` — contains `enabled`, `direction`, `lots`, `entry_price`, `effective_delta`, `unrealized_pnl`, `realized_pnl`, `trade_count`, `last_rebalance`, `btc_spot`
- All timestamps in IST (UTC+5:30) via `_to_ist()` / `_to_ist_short()` helpers
- Mirrors format of `MONEY_POWER_CALCULATION_LOGIC.md` Section 16
- Output consumed by `GET /api/mmm/session/<id>/walkthrough` and frontend `MMMAlgoCalculations.js`

**Walkthrough entry returned dict now includes these additional top-level keys:**
```python
{
  'type': str,                # entry type (standard/reversal/shift/close_at_5/none/…)
  'summary': str,             # one-line summary
  'calculation': str,         # \n-joined trigger check section
  'details': list[str],       # all other section lines
  'triggers': {               # enriched trigger dict now includes:
    'ce_excess_pct': float,   #   how far CE is above threshold (% excess)
    'pe_excess_pct': float,   #   how far PE is above threshold (% excess)
    'ce_threshold_abs': float,#   absolute BTC threshold for CE
    'pe_threshold_abs': float,#   absolute BTC threshold for PE
    'min_trigger_move_pct': float,  # param value
  },
  'state': dict,              # session snapshot including circuit_state, net_pnl, etc.
  'regime': dict | None,      # regime_info passed in (vol/gamma/trend state)
  'margin': dict | None,      # margin_info passed in (tier/utilization)
  'perp_hedge': dict | None,  # perp_hedge_info passed in (delta hedge state)
  'wind_down_active': bool,   # whether wind-down mode was active this heartbeat
  'adaptive_tier': str | None,# adaptive interval tier name
  'interval': int | None,     # effective heartbeat interval in seconds
}
```

**Sections emitted per heartbeat (all shown in frontend `MMMAlgoCalculations.js`):**
1. `── Heartbeat Interval ──` — effective interval, adaptive tier name, flags (theta-accel, margin-rapid-check)
2. `── Trigger Check (§7) ──` — full threshold formula with absolute values and excess %, YES/NO per side
3. `── Reversal Check (§9) ──` — Case A vs Case B, per-fill comparison, loss P&L check
4. `── Loss Calculation (§5.2) ──` — active_lots breakdown (orig+adj+shifted), formula with values
5. `── Strike Check (§5.3) ──` — old_premium vs shift_threshold, shift_target if triggered
6. `── Lots Calculation (§5.4) ──` — raw→buffer→ceil→cap chain
7. `── Execution & Verification (§5.5) ──` — fill price, premium_collected formula, ✓/⚠ vs loss_to_cover
8. `── Regime Controls (§24) ──` — vol/gamma/trend sub-states, action, observation mode
9. `── Margin Guardian (§25) ──` — tier icon, utilization%, net_equity, blocking status
10. `── Wind-Down Mode (§4.2) ──` — ATM vs time-based trigger, threshold%, floor action
11. `── Perp Delta Hedge (§23) ──` — direction, lots, entry, delta, threshold, mode, P&L
12. `── Close-at-5 (§11) ──` — per-position: entry→close price, lots, realized P&L
13. `── Safety Checks (§13-14) ──` — per-event with level icon ⚠/❌/ℹ
14. `── State After Heartbeat ──` — CE/PE lots, triggers, adj_count, total_premium, P&L, circuit_state

### 6.29 mmm_watchdog.py (Added Feb 18, 2026, ~369 lines)
- External supervisor thread watching all active `MMMMonitor` instances
- Detection criteria: (1) thread death, (2) beat timeout (3× interval), (3) status inconsistency
- On detection: emits `mmm_safety` WebSocket event → logs activity → stops dead monitor → restarts fresh monitor
- Records restart in `session['_watchdog_restarts']` for audit
- Does **NOT** restart PAUSED sessions — only RUNNING sessions whose threads died
- Config: `WATCHDOG_POLL_INTERVAL`, `BEAT_TIMEOUT_MULTIPLIER = 3`

### 6.30 mmm_perp_hedge.py (Added Feb 22, 2026, ~441 lines)
- `PerpHedgeManager` class — one instance per session, managed by monitor
- `_calculate_portfolio_delta(session, premiums)` → net delta across ALL open positions (uses Greeks from options chain)
- `_compute_hedge_lots(effective_delta)` → target perp lots to neutralize delta (ratio-adjusted)
- `check_and_rebalance(session)` → main entry point called from monitor heartbeat
  - Computes delta, checks threshold (`perp_hedge_delta_threshold`), checks cooldown
  - Places/adjusts/closes perp position via `rest_client.place_order_by_symbol()` (BTCUSD)
  - Direction flips are atomic: close existing → open opposite in one heartbeat
- `close_hedge(session)` → graceful close (wind-down, stop, max-loss)
- `get_hedge_status(session)` → returns current state dict for API/WebSocket
- Safety: max lots cap, cooldown timer, stale-delta skip (when `_pnl_calculation_incomplete`)
- Perp P&L included in session total for max-loss and trailing-stop checks
- Emits: `mmm_perp_hedge_update`, `mmm_perp_hedge_execution`, `mmm_perp_hedge_flip`

### 6.31 mmm_harvester.py (Added March 3, 2026, ~246 lines)
- `scan_harvestable_positions(session, fetch_premium_fn)` → main entry, scans BOTH sides
  - Checks `harvest_enabled`, capacity pressure ≥ `harvest_pressure_threshold`
  - Filters: profit_pct ≥ `harvest_profit_pct`, age ≥ `harvest_min_age_mins`, not `_being_closed`
  - Scores by `harvest_score = profit_pct × age_score × premium_weight`
  - Returns sorted list capped at `harvest_max_per_beat`
- `get_effective_harvest_params(session, side, params)` → M3 Asymmetry modifier
  - Computes call/put lot ratio, checks `rebalance_asymmetry_threshold`
  - Extreme boost: profit_pct × 0.6, max_per_beat=5, pressure_threshold=0.3
  - Moderate boost: profit_pct × 0.8, max_per_beat=4, pressure_threshold=0.5
  - Only boosts on the heavier side
- Called from `mmm_monitor.py: _process_harvest()` (~line 3129)

### 6.33 mmm_dte_presets.py (Added March 12, 2026, ~306 lines)
- Central module for multi-expiry (multi-DTE) support
- `DTE_PRESETS` dict: `0DTE` and `5DTE` presets (each defines `interval`, `wind_down_hours_before_expiry`, `close_at_threshold`, `max_adjustments`, `description`, `dte_range`)
- `apply_preset(preset_name, user_params)` → merges preset defaults with user overrides (user always wins)
- `list_presets()` → returns list of preset names + descriptions + details
- `check_aggregate_pnl(sessions, global_max_loss)` → checks combined realized + unrealized P&L across all active sessions, returns `{safe, level, combined_pnl, global_max_loss, pct_used, detail}`
- `check_chain_liquidity(chain, strike, min_bid, min_bid_size)` → validates nested chain format `{strike, call:{bid, bid_size}, put:{bid, bid_size}}`
- `compute_total_dte_hours(expiry_str)` → hours from now to expiry
- `infer_dte_category(total_dte_hours)` → `'0DTE'` if ≤36h, `'5DTE'` if ≤168h, `'20DTE'` otherwise
- Standalone module — imported by `mmm_state.py`, `mmm_api.py`

### 6.32 mmm_recycler.py (Added March 3, 2026, ~514 lines)
- `select_recyclable_positions(session, hedge_side)` → filters frozen adjustment positions
  - Excludes `_being_closed`, original positions (if `recycle_protect_original=True`), zero-lot positions
  - Sorts by `entry_premium` ascending (cheapest first)
- `check_recycle_viability(recyclable_with_prices, loss_to_hedge, new_premium, ...)` → 3 checks
  - Premium ratio, net lot gain, affordability — all must pass
  - **Check 3 uses `current_active_lots`** (Split Ledger: only active count, not total)
  - Returns `(viable, reason, details_dict)` tuple
- `execute_lot_recycling(session, aggressor, hedge_side, loss_to_hedge, ...)` → async two-phase operation
  - Phase A: Buyback selected frozen positions via `close_position()`
  - Phase B: Sell fewer lots at new strike via `execute_adjustment()` — uses `active_lots` for cap check
  - Cooldown enforcement: `recycle_cooldown_sec`
  - Margin tier guard: only GREEN/YELLOW (checked in `_process_lot_recycling()`)
  - `recycle_count` incremented on SUCCESS only; `recycle_attempt_count` on failure
- Called from `mmm_monitor.py: _process_adjustment()` (~line 2610) when "Position cap reached"
- Also called from `mmm_monitor.py: _process_lot_recycling()` (~line 3247)

### 6.34 mmm_breakeven_engine.py (Added March 15, 2026, ~605 lines)

Real-time portfolio breakeven awareness module. Computes lower and upper BTC spot prices where total portfolio P&L = 0, classifies risk zones, and provides aggression multipliers for lot calculation.

**Key class:** `BreakevenEngine` (singleton via `get_breakeven_engine()`)

**Public methods:**
- `compute_breakeven(session, spot_price)` → `BreakevenResult` dict (23 fields)
  - Intrinsic-only P&L model: `(entry_premium - max(intrinsic, 0)) × lots × 0.001`
  - Includes all positions (active + frozen) + perp hedge + realized_pnl
  - Position-change caching with MD5 hash — full scan+bisection ~1ms, cached read ~0.01ms
  - Dynamic scan range: auto-expands to 120% beyond furthest strike
  - Coarse scan (~80 points) + binary search ($10 precision convergence)
  - Returns: `lower_breakeven`, `upper_breakeven`, `nearest_distance_pct`, `zone`, `multiplier`, `band_width_pct`, `band_contracting`, `is_narrow_band`, etc.
- `get_aggression_multiplier(result)` → float (1.0–`breakeven_aggression_max`)
  - Non-directional: applies to ALL triggered adjustments
  - Zones: SAFE (1.0×) → WARNING (1.0–1.3×) → DANGER (1.3–2.0×) → CRITICAL (2.0–max×)
  - Linear interpolation prevents lot-count flip-flops at zone boundaries
- `invalidate_cache(session_id)` → None
  - Called after position-changing events to force next scan+bisection
  - 8 call sites: adjustment fill, strike shift fill, shift fallback fill, close-at-5, harvest, lot recycle, shift-time recycle, operator inject

**Integration points:**
- `mmm_monitor.py` Step 5.7: Calls `compute_breakeven()` every heartbeat (when enabled)
- `mmm_engine.py` Step 4: Reads `session['_breakeven_multiplier']` and applies to raw_lots
- `mmm_engine.py` Step 5a: Combined ceiling caps `gamma_mult × breakeven_mult × trend_mult`
- `mmm_websocket.py`: Standalone `mmm_breakeven` event + embedded in `mmm_heartbeat` payload
- `mmm_api.py`: GET `/api/mmm/session/<id>/breakeven` endpoint

**Session state keys:**
- `_breakeven_result` (dict): Full BreakevenResult from last computation
- `_breakeven_multiplier` (float): Aggression multiplier for lot calculation
- `_breakeven_zone` (str): 'SAFE' / 'WARNING' / 'DANGER' / 'CRITICAL'
- `_breakeven_zone_prev` (str): Previous zone for transition detection

**Activity types:** `breakeven_zone_change`, `breakeven_band_contracting`, `breakeven_narrow_band`

---

## 7. FRONTEND COMPONENT DETAILS

### 7.1 MMMDashboard.js (Main Container)
- **Header:** Title, BTC Options badge, health indicator, connection status, New Session + Refresh buttons
- **Left Panel:** Session list with 3 tabs (Active/Idle/History), session cards with controls + DTE category chip (non-0DTE sessions)
- **Right Panel:** Session detail with multiple tabs (Overview/Positions/Triggers/Adjustments/P&L/Safety/Strike Map/Algo Calculations/Consolidated/Greeks & IV/Activity/Regime/Margin/Perp Hedge/Analytics)
- **Dialogs:** CreateSessionDialog (expiry dropdown, DTE preset dropdown, mode: Fresh/Import/Adopt), BothSidesAlert, MMMSettingsDialog
- **State:** Uses `useMMM()` from MMMContext + `useMMMWebSocket(sessionId)` for live data

### 7.2 CreateSessionDialog (inside MMMDashboard.js)
- Fetches expiries from `/api/mmm/expiries` on open → shows as Select dropdown
- Fetches DTE presets from `/api/mmm/dte-presets` on open → shows as DTE Preset dropdown
- Selecting a preset auto-fills interval, wind-down, close-at threshold, max adjustments from preset defaults
- Shows BTC spot price from `/api/mmm/spot-price`
- Mode dropdown: Fresh (auto-find), Import (existing positions), or Adopt (from exchange)
- Core Parameters: desired CE/PE premium, initial lots, expiry (dropdown), interval, max loss
- Creates session via `mmmService.createSession(config)` with `dte_category` included

### 7.3 MMMConfigPanel.js (~866 lines)
- Shown for IDLE/STOPPED sessions in the detail panel
- 3 modes: Auto-Find / Manual Select / Import Existing
- **Auto-Find:** Expiry dropdown + CE/PE desired premium + Find button → StrikePreviewTable → Confirm & Initialize
- **Manual Select:** MMMStrikeSelector component (browse full chain)
- **Import Existing:** CE/PE fields for Strike, Fill Price, Symbol → Import & Initialize
- Entry Summary: total premium calculation before confirm

### 7.4 MMMContext.js (~449 lines)
- `MMMProvider({ children, socket })` — wraps dashboard
- Manages: sessions array, selectedSessionId, loading, error, healthStatus, connectionStatus, paramsInfo, bothSidesAlert
- Fetches sessions on mount, auto-refreshes every 30s
- WebSocket listeners for all 17 `mmm_*` events
- `useMMM()` hook — throws if used outside MMMProvider

### 7.5 MMMActivityFeed.js
- Displays real-time ring buffer of background activity events
- Connects to `GET /api/mmm/activities` + `mmm_activity` WebSocket events
- Shows: order placement, fill waits, repricing, heartbeat execution, adjustments, safety events, shift-time recycle events
- Color-coded by activity type; max 200 entries shown

### 7.5b MMMSafetyPanel.js (~333 lines)
- **Split Ledger display:** CE/PE position indicators show `active_lots` vs `max_lots_per_side` cap, with frozen count displayed separately
- Frozen count indicator: shows frozen lots when > 0
- Max total exposure indicator: shows `active + frozen` vs `max_total_exposure` ceiling
- Asymmetry check uses `total_lots` (active + frozen) matching backend behavior
- Also shows: max adjustments, max loss, whipsaw, near-expiry, trailing profit, pnl guardrail, margin tier

### 7.6 MMMAdoptPanel.js
- UI for "Adopt" mode: fetch open exchange positions, display in table, user selects which to adopt
- Calls `GET /api/mmm/exchange-positions` → table of open short BTC options
- User selects CE/PE positions → `POST /api/mmm/session/<id>/adopt`
- Shows: symbol, strike, lots, entry price, mark price, unrealized P&L

### 7.7 MMMAlgoCalculations.js (Enhanced — Feb 2026)
- Displays the algo walkthrough log from `GET /api/mmm/session/<id>/walkthrough`
- Shows per-heartbeat calculation steps in human-readable format (IST timestamps)
- Dashboard "Algo Calculations" tab
- **New features added in Feb 2026 enhancement:**
  - **Collapsible cards** — each entry is collapsed by default (click header to expand); latest entry auto-expanded
  - **Filter chips** — click any type chip to filter to only that entry type (ENTRY/STANDARD/REVERSAL/etc.); multiple filters are OR-combined; "Clear filters" chip resets
  - **Search box** — full-text search across calculation + details; matches highlighted
  - **Stats bar** — shows Net P&L, Realized, Total Premium (BTC), Adj Count, Last Aggressor, CE/PE lots from the most recent entry's `state` field; regime/margin alerts shown if non-GREEN
  - **Export button** — downloads all visible (filtered) entries as a `.txt` file
  - **Section-aware line coloring** — lines starting with `──` are colored by section type (Trigger=blue, Regime=orange, Margin=pink, Perp=cyan, Safety=red, etc.)
  - **Rich entry card headers** — show regime action badge (orange/red when not NORMAL), margin tier badge (yellow/red when not GREEN), wind-down badge (teal when active), perp hedge direction badge, adaptive interval tier badge
  - **New TYPE_COLORS entries**: `wind_down` (teal), `regime_blocked` (orange-brown)
  - **`useMemo`-based filtering** — entries filtered+searched without re-fetching

### 7.8 MMMAnalyticsPanel.js + MMMAnalyticsSummary.js + MMMAnalyticsTable.js
- Three-part analytics view: summary cards + aggregated stats + historical table
- Capital planning, risk profiling, strategy validation from real historical sessions
- Data via analytics API endpoints (Section 4.10)

### 7.9 MMMMarginGuardianPanel.js
- Displays real-time margin utilization from `GET /api/mmm/session/<id>/margin`
- Tier indicator (GREEN/YELLOW/ORANGE/RED/CRITICAL) with color coding
- Shows: utilization %, position margin, order margin, net equity
- Updates via heartbeat WebSocket

### 7.10 MMMRegimePanel.js
- Displays regime status from `GET /api/mmm/session/<id>/regime`
- Three regime indicators: Volatility, Gamma, Trend
- Aggregate action badge (NORMAL / WARN / BLOCK / EMERGENCY)
- Updates via `mmm_regime` WebSocket events

### 7.13 MMMPerpHedgePanel.js (Added Feb 22, 2026)
- Displays perp hedge state from `GET /api/mmm/session/<id>/hedge/status`
- Shows: direction (LONG/SHORT/FLAT), lots, entry price, effective delta, unrealized/realized P&L
- Toggle button to enable/disable perp hedge
- Close button to exit perp position immediately
- Updates via `mmm_perp_hedge_update`, `mmm_perp_hedge_execution`, `mmm_perp_hedge_flip` WebSocket events
- Parameter display for delta threshold, ratio, rebalance band, max lots, cooldown

### 7.12 MMMConsolidatedPositions.js
- Groups scattered individual fills by (side, strike) into consolidated rows
- Shows: Side, Strike, Total Lots, Notional BTC, Weighted Avg Entry, Current Premium, P&L
- Pure frontend aggregation — reuses `buildPositionRows()` from MMMPositionsTable

### 7.14 MMMGreeksPanel.js
- Fetches live Greeks (δ, γ, θ, ν) and IV from `/greeks-iv` endpoint
- Portfolio-weighted totals row (lots × per-contract greek)
- Color-coded: blue δ, purple γ, green θ, orange ν, red IV
- Auto-refreshes every 60s, manual refresh button with timestamp
- Greeks converted from per-1-BTC ticker values to per-lot position Greeks (× LOT_SIZE_BTC × -1 for short)

### 7.15 MMMEducation.js
- Educational tooltips, explanations, and guides embedded in the dashboard
- Explains core concepts (trigger, shift, reversal, etc.) in plain language

### 7.16 Key UI Patterns
- **Socket prop flow:** App.js `connectionManagerRef.current?.socket` → `<MMMProvider socket={socket}>` → MMMContext attaches listeners
- **Lazy loading:** `MMMDashboard` loaded via `React.lazy()` with `Suspense` fallback
- **Error isolation:** `MMMErrorBoundary` wraps everything, prevents MMM crashes from affecting main app
- **Status colors:** IDLE=gray, RUNNING=green, PAUSED=orange, BOTH_SIDES_UP=red, STOPPED=dark gray
- **Data flow:** REST API for initial load + actions, WebSocket for real-time updates

### 7.17 MMMSettingsDialog.js (~669 lines)
- 7 parameter groups: Core, Triggers, Safety, Expiry, Adaptive, Wind-Down, Position Lifecycle (Split Ledger)
- Rich `PARAM_TOOLTIPS` map with `?` help icons for every parameter including 5 Split Ledger params
- `DialogContent` with `maxHeight: '75vh'` + `overflowY: 'auto'` for scrollability
- Select input for `wind_down_floor_action` (close_all / stop_adjustments / alert)
- Position Lifecycle section includes M1/M2/M3 params + Split Ledger shift-time recycle params
- Safety section includes `max_total_exposure` with tooltip explaining auto mode and M2 non-trigger

### 7.18 MMMStatusBanner.js
- Adaptive tier badge (`⚡ 10-20h`) showing current heartbeat interval range
- Wind-down badge (`🌙 Wind-Down`) when wind-down mode is active
- Regime warning badge when regime action is WARN or BLOCK

### 7.19 MMMBreakevenPanel.js (Added March 15, 2026, ~317 lines)

Displays real-time portfolio breakeven awareness with visual band representation and risk zone classification.

**Compact view:**
- **Horizontal band bar** — Gray track showing lower breakeven, spot marker, upper breakeven
- **Zone-colored band** — Region between breakevens colored by zone (green/amber/red/deep-red)
- **Spot marker** — White circle with zone-colored border, positioned proportionally within band
- **Price labels** — USD prices for lower BE, spot, upper BE below the bar
- **Distance indicators** — `"Lower: X% ($Y)"` and `"Upper: X% ($Y)"` showing distance percentages

**Expanded view (click expand arrow):**
- **8-field details table:** Lower BE, Upper BE, Nearest Side, Nearest Distance, Band Width, Aggression Multiplier, P&L at Spot, Positions Count
- **Band contracting warning** (orange chip) — Band width shrunk >30% since last position change
- **Narrow band warning** (yellow chip) — Band width < `breakeven_narrow_band_threshold` (default 5% of spot)
- **Cached indicator** — Shows when data is from cache vs freshly computed

**Zone colors:**
- SAFE: `#4caf50` (green) — Distance > `breakeven_warning_pct`
- WARNING: `#ff9800` (amber) — Distance ≤ warning, > danger
- DANGER: `#f44336` (red) — Distance ≤ danger, > critical
- CRITICAL: `#d32f2f` (deep red) — Distance ≤ `breakeven_critical_pct`

**Data source:** Props-driven from `MMMDashboard`, receives `heartbeat?.breakeven || session._breakeven_result`

**Conditional render:** Only shown when `session.params?.breakeven_control_enabled || heartbeat?.breakeven?.enabled`

**Integration:** Imported by `MMMDashboard.js`, rendered after positions table on live session dashboards

---

## 8. DATA FLOW

### 8.1 Session Lifecycle

```
User clicks "+ New Session"
  → CreateSessionDialog opens
  → User selects mode (Fresh/Import/Adopt), expiry, params
  → POST /api/mmm/session/create
  → Session created with status=IDLE
  → If import/adopt mode: sides initialized immediately

User selects session (IDLE) → ConfigPanel shown
  → Auto-Find: preview strikes → confirm → init-fresh
  → Manual: browse chain → select → init-fresh
  → Import: enter data → init-import
  → Adopt: browse exchange positions → confirm → adopt

User clicks Start
  → POST /api/mmm/session/<id>/start
  → MMMMonitor starts background thread
  → MMMWatchdog supervises the monitor thread
  → status = RUNNING
  → Heartbeat loop begins

Running → every interval:
  → Monitor fetches prices (via circuit breaker)
  → Runs close-at-5, wind-down, regime, margin guardian, safety
  → Pending order guard checks in-flight orders
  → Evaluates triggers
  → If adjustment needed → executes, updates state, records walkthrough + activity
  → Perp hedge: check_and_rebalance() if enabled (after trigger evaluation)
  → Emits WebSocket events (incl. perp hedge updates) → frontend updates in real-time
  → Heartbeat health tracker records beat outcome

User can: Pause/Resume/Stop/Change params/Force heartbeat/Reduce position
```

### 8.2 Options Chain Data

MMM uses `OptionsChainService` (existing codebase) to fetch:
- Available expiry dates
- BTC spot price
- Full options chain (strikes, bids, asks, greeks)

This is the same service used by the Options Chain Panel in the main WebUI. MMM lazy-loads it to avoid circular imports.

### 8.3 Adopt Flow

```
User opens Adopt UI (MMMAdoptPanel.js)
  → GET /api/mmm/exchange-positions
  → mmm_adopter.fetch_exchange_btc_options()
  → DeltaClient fetches open short BTC option positions
  → User selects CE/PE positions from table
  → POST /api/mmm/session/<id>/adopt
  → mmm_adopter.build_adopted_session_state()
  → Session initialized; trigger snapshots = current prices
  → Behaves identically to imported session going forward
```

---

## 9. OPERATIONS & DEPLOYMENT

### 9.1 Backend

- **Flask app:** `webui/backend/app.py` on port 5555
- **LaunchAgent:** `com.gridbot.webui` (auto-restart on crash)
- **Restart:** `launchctl stop com.gridbot.webui && sleep 3 && launchctl start com.gridbot.webui`
- **Blueprint registration:** Lines 476-487 in app.py (try/except isolated)
- **Session data:** Persisted to `data/mmm_sessions.db` (SQLite)
  - Legacy `data/mmm_sessions.json` auto-migrated to `.json.migrated` on first run
- **Activity log:** `data/mmm_activity_log.json` (ring buffer, max 200)
- **Logs:** Standard Python logging, prefix `[MMM]`

### 9.2 Frontend

- **Build:** `cd webui/frontend && npm run build` (react-app-rewired)
- **Served:** Flask serves production build from `webui/frontend/build/`
- **Dev mode:** `npm start` on port 3000 with proxy to 5555
- **After code changes:** Must rebuild and restart backend for production

### 9.3 Verification Commands

```bash
# Health check
curl -s http://localhost:5555/api/mmm/health | python3 -m json.tool

# List expiries
curl -s http://localhost:5555/api/mmm/expiries | python3 -m json.tool

# List sessions
curl -s http://localhost:5555/api/mmm/sessions | python3 -m json.tool

# BTC spot price
curl -s http://localhost:5555/api/mmm/spot-price | python3 -m json.tool

# Activity log
curl -s http://localhost:5555/api/mmm/activities | python3 -m json.tool

# Exchange positions (for adopt)
curl -s http://localhost:5555/api/mmm/exchange-positions | python3 -m json.tool

# Import test
python3 -c "from webui.backend.routes.mmm import mmm_bp, init_mmm; print('OK')"
```

---

## 10. COMMON ISSUES & FIXES

### 10.1 "MMM tab doesn't appear"
- Check `App.js` has lazy import, tab definition, and sectionContent for 'mmm'
- Ensure `<MMMProvider socket={socket}>` wraps `<MMMDashboard />`
- Rebuild frontend: `cd webui/frontend && npm run build`
- Restart backend: `launchctl stop/start com.gridbot.webui`

### 10.2 "API returns 404 for /api/mmm/*"
- Backend hasn't been restarted since MMM code was added
- Check `app.py` has blueprint registration
- Run import test: `python3 -c "from webui.backend.routes.mmm import mmm_bp"`

### 10.3 "Expiry dropdown empty"
- API `/api/mmm/expiries` must return data from OptionsChainService
- Check if Delta Exchange API is reachable
- Verify `mmm_initializer.py` can access `OptionsChainService`

### 10.4 "WebSocket events not arriving"
- Ensure `MMMProvider` receives the socket prop from App.js
- Socket is `connectionManagerRef.current?.socket` (check App.js for exact line)
- Check browser console for socket.io connection errors

### 10.5 "ConfigPanel not showing for IDLE session"
- Dashboard condition checks `fullSession.strategy_status || fullSession.status`
- ConfigPanel checks `sessionStatus` against 'IDLE', 'STOPPED' (case-insensitive)
- Backend uses uppercase status values (IDLE, RUNNING, etc.)

### 10.6 "Session won't start"
- Session must be initialized first (init-fresh, init-import, or adopt)
- Check that CE and PE sides have strike/premium/lots set
- Verify MMMMonitor can start a background thread

### 10.7 "Sessions disappeared after backend restart"
- Sessions are in `data/mmm_sessions.db` (SQLite). Check if file exists and is not corrupted.
- If `data/mmm_sessions.json.migrated` exists, migration already ran (that's correct).
- Running sessions are auto-restored by `init_mmm()` on startup.

### 10.8 "Monitor died and session appears stuck (RUNNING but no heartbeat)"
- MMMWatchdog should auto-restart within `WATCHDOG_POLL_INTERVAL` seconds
- Check `session['_watchdog_restarts']` counter — if > 0, watchdog restarted it
- Check `GET /api/mmm/session/<id>/beat-health` for last beat timestamp and health grade
- If watchdog not running, check `__init__.py` → `init_mmm()` for watchdog start

### 10.9 "Circuit breaker tripped — algo seems paused"
- Check `GET /api/mmm/session/<id>/beat-health` for consecutive failure count
- Circuit breaker OPEN = partial-beat mode (close-at-5 + safety only with cached prices)
- It self-heals after 30s when exchange API recovers
- Check exchange connectivity; circuit breaker never terminates the session

### 10.10 "Margin CRITICAL — session auto-stopped"
- `mmm_margin_guardian.py` stopped session due to CRITICAL margin tier
- Check `GET /api/mmm/exchange/margin` for current utilization
- Reduce exchange positions before restarting
- Tier thresholds are configurable in session params (margin settings)

---

## 11. EXTENSION GUIDE

### 11.1 Adding a New Safety Check
1. Add method in `mmm_safety.py` following existing pattern
2. Call it from `mmm_monitor.py` heartbeat loop (step 4)
3. Add WebSocket emission via `emit_safety()`
4. Add indicator in `MMMSafetyPanel.js`

### 11.2 Adding a New API Endpoint
1. Add route in `mmm_api.py` under appropriate section
2. Add service method in `mmmService.js`
3. Call from appropriate frontend component

### 11.3 Adding a New WebSocket Event
1. Add emitter function in `mmm_websocket.py`
2. Add listener in `MMMContext.js` (useEffect socket.on)
3. Pass data through context to consuming component

### 11.4 Modifying Adjustment Logic
- Core math is in `mmm_engine.py`
- Reversal logic is in `mmm_reversal.py`
- Trigger evaluation is in `mmm_trigger.py`
- All formulas reference sections in `MONEY_POWER_CALCULATION_LOGIC.md`

### 11.5 Adding a New Parameter
1. Add to `PARAM_RULES` in `mmm_config.py` (type, default, range, hot_reload flag)
2. Add to `create_session()` in `mmm_state.py` default params dict
3. Add to `MMMSettingsDialog.js` in the appropriate parameter group + tooltip
4. Use `session['params']['your_param']` in the relevant module

### 11.6 Adding a New Activity Type
1. Add to `ACTIVITY_TYPES` dict in `mmm_activity.py`
2. Log events via the activity module's log function from any module
3. The event appears automatically in `MMMActivityFeed.js`

---

## 12. KEY DESIGN DECISIONS

1. **Complete isolation:** MMM has zero imports from/to existing codebase (except App.js integration and OptionsChainService). Failures in MMM never crash the main app.

2. **Per-fill P&L on reversal:** Unlike averaging, each adjustment fill's P&L is computed at its actual strike's current premium. Accurate across multiple strikes and shifts.

3. **Both-sides-up requires human judgment:** The algo pauses and waits. No automatic action in the most dangerous scenario.

4. **Triggers update on BOTH sides:** After every adjustment, both CE and PE snapshots reset. This ensures the "safe zone" expands correctly.

5. **ALL positions always included in loss calculations:** Active positions AND shifted positions at old strikes are ALL evaluated at their live premiums in the standard adjustment formula. No position is ever excluded. The `shift_threshold` only controls where to open NEW positions.

6. **Close-at-5 runs on ALL positions:** Active, adjustment, and shifted — across all strikes. Any position at ≤5 gets closed for profit.

7. **Ceiling rounding + buffer:** Lots calculation always rounds up (ceil) and adds buffer%. Never under-hedged.

8. **Socket prop from App.js:** MMMProvider doesn't create its own socket connection — it receives the app's existing socket, avoiding duplicate connections.

9. **SQLite over JSON:** Session state persisted in SQLite for atomic hot-reload (`params_json` and `data_json` stored separately). Legacy JSON auto-migrated on first run.

10. **Circuit breaker never kills sessions:** API failures trigger graduated partial-beat or full-skip. The session survives and self-heals. Only margin guardian (CRITICAL tier) and safety checks (max loss, near-expiry) terminate sessions.

11. **Watchdog is external:** Runs as a separate supervisor thread, not inside the monitor. Can detect and restart a completely dead monitor thread from the outside.

12. **Adopt = import from exchange:** Adopted sessions are state-equivalent to imported sessions. All runtime modules treat them identically. The only difference is HOW initial state was constructed.

13. **Regime controls are pre-adjustment only:** They block NEW adjustments but do NOT force close existing positions (that is the margin guardian's job). Close-at-5 and wind-down run regardless of regime state.

14. **Perp hedge runs independently of regime:** Regime may block option adjustments, but the perp hedge always runs because it IS the defense when regime blocks. This is the institutional approach — perps absorb directional risk while options collect theta.

15. **Decimal arithmetic for P&L accumulation:** All P&L computations use `Decimal` via `_D(x)` helper (converts through `str(x)` to avoid IEEE 754 float artifacts). Eliminates $0.50–$1.00 drift over session lifetime.

16. **Unified Position Ledger:** `positions[]` list is the single authoritative source for all position data. All computed views (`active_lots`, `total_lots`, `frozen_total_lots`, etc.) are derived via `recompute_side_lots()`. ID-based removal via `_pos_id`. Auto-migration adds `_pos_id` and `position_type` to legacy data.

17. **Lot lifecycle is non-destructive:** M1 harvesting and M2 recycling never force-close profitable positions. M1 only closes when profit ≥ threshold AND position is old enough. M2 only recycles when all three viability checks pass. `recycle_protect_original=true` by default ensures the user's original entry is never recycled. `recycle_count` only increments on success — analytics distinguish attempts from completions.

18. **Split Ledger principle:** Position cap (`max_lots_per_side`) checks only `active_lots`, not `total_lots`. Frozen positions are dead weight from old strikes and should not block new hedging at the current strike. `max_total_exposure` provides a safety ceiling for `active + frozen` combined (default 0 = auto 2×cap). The "Total exposure ceiling" error message intentionally differs from "Position cap reached" to avoid false M2 recycle triggers. Shift-Time Recycle proactively cleans frozen positions during strike shifts (disabled by default).

---

## 13. TESTING

Test files in `webui/backend/routes/mmm/tests/`:

| File | What It Tests |
|------|--------------|
| `test_mmm_engine.py` | Loss calc, lots, ceiling, buffer, P&L |
| `test_mmm_reversal.py` | Detection, cooldown, skip, multi-cycle |
| `test_mmm_strike_shift.py` | Shift detection, freeze, new strike |
| `test_mmm_close_at_5.py` | Scan, close, side closed, both closed |
| `test_mmm_safety.py` | All safety mechanisms |
| `test_mmm_integration.py` | State, config, triggers, storage |
| `test_mmm_state.py` | Position migration, side state, recompute |
| `test_mmm_trigger.py` | Trigger evaluation, theta accel, adaptive interval |
| `test_mmm_wind_down.py` | Wind-down activation, LIFO close, thresholds |
| `test_mmm_harvester.py` | M1 profit harvest scanning, M3 asymmetry boosting (24 tests) |
| `test_mmm_recycler.py` | M2 position selection, viability checks, two-phase execution, Split Ledger active_lots (31 tests) |
| `test_mmm_lot_lifecycle_integration.py` | All 15 lot lifecycle params in DEFAULT_PARAMS, HOT_RELOAD_PARAMS, PARAM_RULES (12 tests) |
| `test_mmm_dte_presets.py` | DTE presets, aggregate PnL, liquidity gate, DTE computation, v2 near-expiry, v2 adaptive interval/theta (30 tests) |

**Note:** Tests use `--import-mode=importlib` (via `pytest.ini`) and direct module loading via `importlib.util` to bypass `routes/__init__.py` Flask dependencies. The `tests/__init__.py` must NOT exist — its presence causes pytest to walk up the package chain and trigger Flask imports.

Run: `cd webui/backend/routes/mmm/tests && python -m pytest -v`

---

## 14. MODULE DEPENDENCY MAP

```
mmm_monitor.py (orchestrator — 5533 lines)
  ├── mmm_trigger.py             evaluate triggers + adaptive interval
  ├── mmm_engine.py              core adjustment math (~763 lines)
  │     └── mmm_reversal.py        reversal detection
  ├── mmm_strike_shift.py        freeze/shift strikes
  ├── mmm_close_at_5.py          position buyback
  ├── mmm_safety.py              all safety checks (~739 lines)
  ├── mmm_wind_down.py           LIFO wind-down
  ├── mmm_regime.py              vol/gamma/trend controls
  ├── mmm_circuit_breaker.py     wraps exchange API calls
  ├── mmm_pending_orders.py      guards before executor
  ├── mmm_executor.py            order placement
  ├── mmm_perp_hedge.py          perpetual futures delta hedge
  ├── mmm_harvester.py           M1 profit harvesting + M3 asymmetry scan
  ├── mmm_recycler.py            M2 lot recycling (two-phase execution, ~514 lines)
  │     ├── mmm_close_at_5.py      Phase A buyback (local import)
  │     └── mmm_strike_shift.py    Phase B strike selection (local import)
  ├── mmm_walkthrough.py         logs calculation steps
  ├── mmm_activity.py            logs background events
  ├── mmm_websocket.py           emits all 22 events
  ├── mmm_heartbeat_health.py    beat telemetry (pure observability)
  └── mmm_margin_guardian.py     tier-based margin enforcement
        └── mmm_telegram.py        alert notifications

mmm_api.py (REST layer — 3398 lines)
  ├── mmm_storage.py (SQLite)
  ├── mmm_initializer.py
  ├── mmm_executor.py
  ├── mmm_adopter.py
  ├── mmm_analytics_aggregator.py
  ├── mmm_analytics_storage.py
  └── mmm_activity.py

mmm_watchdog.py (supervisor thread, started by __init__.py)
  └── monitors all MMMMonitor instances; restarts on death/timeout/inconsistency

mmm_constants.py     ← imported by: engine, adopter, walkthrough, regime, perp_hedge, harvester, recycler
mmm_state.py         ← imported by: api, monitor, initializer (~839 lines)
mmm_config.py        ← imported by: api, state, engine, perp_hedge (~443 lines)
mmm_dte_presets.py   ← imported by: state, api (~306 lines)
```

---

*This document is the single source of truth for any AI agent working on the MMM algorithm. All file paths, module names, API endpoints, WebSocket events, and state fields above have been verified against the actual codebase as of March 12, 2026. Backend: 33 Python files (32 modules + 1 DB). Frontend: 28 React components + 2 hooks + 2 utils. Reference `MONEY_POWER_CALCULATION_LOGIC.md` for the sealed mathematical logic. Reference `MMM_SPLIT_LEDGER_INSTRUCTIONS.md` and `MMM_SPLIT_LEDGER_PLAN.md` for Split Ledger design rationale. Reference `MMM_10_OF_10_PRODUCTION_PLAN.md` for the remaining hardening tasks.*

---

## 15. MARCH 2026 AUDIT FIXES (implemented March 10, 2026)

The following items were implemented as part of a comprehensive audit. All are in production code.

### 15.1 T1 — Safety Fixes

**T1-1: M2 P&L Rollback (`mmm_recycler.py`)**
When Phase B fails (exception or error), both rollback paths now subtract `phase_a_pnl` from `session['realized_pnl']` to undo the P&L added by `close_position()` during Phase A. Without this, failed recycles permanently inflate realized P&L.

**T1-2: Peak P&L Decay Floor (`mmm_safety.py`)**
`update_peak_pnl()` now uses `max(current_peak * 0.9 + total_pnl * 0.1, 0)` — floor at 0 prevents peak decaying below zero when total_pnl is deeply negative, which would permanently suppress the trailing stop.

**T1-3: Consecutive CRITICAL Margin Escalation (`mmm_margin_guardian.py` + `mmm_monitor.py`)**
- `MarginGuardian.check()` tracks `self._consecutive_critical` beats at CRITICAL tier.
- When `consecutive_critical >= consecutive_critical_threshold` (default 3), adds `force_stop_session` to the returned `actions` list and exposes `consecutive_critical` count in the result dict.
- `mmm_monitor.py` heartbeat checks `'force_stop_session' in margin_result['actions']` BEFORE the tier-based RED/CRITICAL block and calls `self.stop()`.
- New param (hot-reloadable): `consecutive_critical_threshold` (default 3).

**T1-4: Session Heartbeat Lock (`mmm_monitor.py`)**
`self._session_lock` (threading.Lock) is already present and protects API-thread reads via `get_session_snapshot()`. The heartbeat intentionally does NOT hold the lock for its full duration (documented at line 714) — this is an accepted trade-off to avoid blocking all API reads for 1–5 seconds.

### 15.2 T2 — Operational Improvements

**T2-1: min_trigger_move Fallback Default (`mmm_trigger.py`)**
The fallback in `evaluate_triggers()` was `params.get('min_trigger_move', 3.0)` — mismatched with `DEFAULT_PARAMS` value of `10.0`. Fixed to `10.0`. Only affects malformed sessions that somehow lack `params`.

**T2-2: Circuit Breaker should_alert — Already Wired**
`self._circuit.should_alert` is already checked at monitor line 651. No change needed.

**T2-3: Fill Price Bounds Check — Already Present**
`_parse_fill_price()` already validates `price <= 0 or price > 1_000_000` at executor line 102. No change needed.

**T2-4: Lot Velocity Limiter (`mmm_safety.py` + `mmm_state.py`)**
New `check_lot_velocity()` method in `MMMSafety`. Counts lots sold in `adjustment_history` over a rolling window. Blocks adjustments if rate exceeds limit.

New params (all hot-reloadable):
- `lot_velocity_enabled` (default `True`) — master switch
- `lot_velocity_limit` (default `10`) — max lots sold in window
- `lot_velocity_window_mins` (default `30`) — rolling window in minutes

Returns `stop_adjustments` action at limit, `continue` warning at 80% of limit.

**T2-5: P&L Attribution Fields (`mmm_state.py`)**
Five new fields added to session at creation:
- `pnl_initial` — P&L from closing original entry positions
- `pnl_adjustment` — P&L from closing adjustment-filled positions
- `pnl_harvest` — P&L from M1 harvesting
- `pnl_recycle` — P&L from M2 Phase A buybacks (net: only on success)
- `pnl_perp` — Mirror of `perp_hedge.realized_pnl`

These fields are initialized to 0.0. Population by `mmm_close_at_5.py`, `mmm_harvester.py`, and `mmm_recycler.py` is a future enhancement.

**T2-6: Analytics Array Cap — Already Done**
`auto_close_events` is already capped at 200 in `mmm_close_at_5.py`. `reversal_timestamps` and `shift_timestamps` are capped at 200 in `mmm_monitor.py`. `safety_trigger_events` is defined but never appended to (dead field).

### 15.3 T3 — Strategic Enhancements

**T3-1: Proactive Shift Scanner (`mmm_monitor.py`)**
New heartbeat step 1.5: `_proactive_shift_scan(ce_now, pe_now)` runs BEFORE close-at-5.

Logic: for each side with `active_lots > 0`, if `close_threshold < premium < shift_threshold`, trigger `_process_strike_shift()` immediately rather than waiting for the opposite side to breach its trigger. Only shifts one side per beat. Marks `session['_proactive_shifted_{side}'] = True` to prevent double-shifting.

New param: `proactive_shift_enabled` (default `True`, hot-reloadable).

**T3-2: Gamma-Aware Lot Multiplier (`mmm_engine.py`)**
`calculate_lots_to_sell()` now applies a multiplier when the aggressor's excess_pct is large:
- excess_pct 50–100%: multiplier 1.1×
- excess_pct 100–200%: multiplier 1.2×
- excess_pct 200%+: multiplier 1.3× (capped by `gamma_aware_max_multiplier`)

Reads `session['_last_trigger_result']` for the aggressor excess_pct (set by `evaluate_triggers()` each heartbeat). Applied BEFORE trend-tier reduction and caps.

New params (hot-reloadable):
- `gamma_aware_enabled` (default `True`)
- `gamma_aware_max_multiplier` (default `1.3`)

**T3-3: Adaptive Whipsaw Guard (`mmm_safety.py` + `mmm_monitor.py`)**
Replaces the old binary whipsaw pause with a graduated score-based system.

**Three rules:**
1. **Time-windowed counting** — Only counts flip-flops within a rolling `whipsaw_window_mins` window (default 30 min). Old flips outside the window are ignored.
2. **Spot-move validation** — A flip only counts as noise if the spot move between adjustments was < `whipsaw_spot_move_pct` (default 0.3%). Genuine large moves don't increase the score.
3. **Graduated response** — Score determines the action level:
   - **NORMAL** (score 0–1): No restrictions
   - **CAUTION** (score ≥ `whipsaw_caution_score`, default 2): Triggers widened by 1.5×
   - **RESTRICT** (score ≥ `whipsaw_restrict_score`, default 3): Triggers widened by 2.0× + lots halved
   - **COOLDOWN** (score ≥ `whipsaw_cooldown_score`, default 4): Skip one adjustment interval, score reduced by 2

**Score mechanics:** +1 per noise flip-flop, -1 per adjustment interval with no noise. Score is stored in `session['_whipsaw_score']`.

**Monitor integration:**
- Before `evaluate_triggers()`: trigger multiplier applied (1.5× at CAUTION, 2.0× at RESTRICT)
- After `calculate_lots_to_sell()`: lots halved at RESTRICT or higher
- `spot` field recorded in `adjustment_history` for post-analysis

**Session state keys:**
- `_whipsaw_score`: Current noise score (int)
- `_whipsaw_last_noise_at`: ISO timestamp of last noise event
- `_whipsaw_skip_until`: ISO timestamp when COOLDOWN skip expires
- `_whipsaw_last_checked_idx`: Last adjustment index processed

**Migration:** Old keys (`_whipsaw_paused_at`, `_whipsaw_checked_up_to`, `_whipsaw_consecutive_alternating`) are auto-cleaned on first `check_whipsaw()` call. Session auto-resumes from old pause state.

### 15.4 T4 — Nice-to-Have

**T4-1: MONEY_POWER_ALGORITHM_PLAN.md Historical Banner**
Added header banner marking the file as historical reference only, pointing to `AI_MMM_CONTEXT.md` as authoritative.

**T4-2: Pending Order TTL Cleanup — Already Done**
`clear_all_pending(self.session_id)` is called in `start()` at monitor line 222, ensuring a fresh pending-order registry on every monitor start.

**T4-3: Pre-Adjustment Delta Projection for Perp (`mmm_perp_hedge.py`)**
`compute_required_hedge()` and `run_perp_hedge()` both accept `projected_lots: int = 0` and `projected_side: str = ''` kwargs. When provided, projected delta from the about-to-execute adjustment is added to portfolio delta before computing the hedge size. Backward-compatible (zero defaults). Controlled by param `perp_hedge_project_adjustment` (default `True`).

**T4-4: Price Basis Documentation — Already Done**
`_fetch_premiums()` docstring documents the intentional mark/bid split: mark price for shift detection (conservative), bid price for close-at-5 (accurate for illiquid buybacks).

### 15.5 New DEFAULT_PARAMS and HOT_RELOAD_PARAMS (March 2026)

All new params are in both `DEFAULT_PARAMS` and `HOT_RELOAD_PARAMS` in `mmm_state.py`:

| Parameter | Default | Description |
|---|---|---|
| `lot_velocity_enabled` | `True` | Master switch for lot velocity limiter |
| `lot_velocity_limit` | `10` | Max lots sold per velocity window |
| `lot_velocity_window_mins` | `30` | Rolling window for velocity check (minutes) |
| `gamma_aware_enabled` | `True` | Master switch for gamma-aware lot multiplier |
| `gamma_aware_max_multiplier` | `1.3` | Cap on multiplier (1.0 = no multiplier) |
| `proactive_shift_enabled` | `True` | Master switch for proactive shift scanner |
| `consecutive_critical_threshold` | `3` | Beats at CRITICAL margin before force-stop |
| `perp_hedge_project_adjustment` | `True` | Include projected adjustment delta in perp hedge |
| `perp_hedge_approx_option_delta` | `0.5` | Approximate option delta for projection |
| `whipsaw_window_mins` | `30` | Rolling window for noise counting (minutes) |
| `whipsaw_spot_move_pct` | `0.3` | Spot move below this % counts as noise |
| `whipsaw_caution_score` | `2` | Score threshold for CAUTION level (triggers ×1.5) |
| `whipsaw_restrict_score` | `3` | Score threshold for RESTRICT level (triggers ×2.0, lots ÷2) |
| `whipsaw_cooldown_score` | `4` | Score threshold for COOLDOWN (skip interval, score -2) |

---

## 16. OPERATOR STRIKE CONTROLS (implemented March 11, 2026)

Three new operator intervention tools added to the Positions tab (Tab 1) of the MMM session dashboard. All require session status `RUNNING` or `PAUSED`.

### 16.1 Operator Position Inject (`POST /api/mmm/session/{id}/inject-position`)

Opens a new short option position on the exchange and registers it in the algo's `positions[]` ledger. The algo manages it going forward as if it had been placed by the bot itself.

**Use case:** Algo missed an entry, operator wants to add exposure while keeping the risk management loop intact, or after closing a risky strike the operator re-establishes farther OTM.

**Body:** `{ side: 'ce'|'pe', lots: int, strike: float }`

**Guards:** Guardian GO signal, session RUNNING/PAUSED, lots cap check (`active_lots` + new ≤ `max_lots_per_side`).

**State changes:** Appends to `positions[]` with `type='manual', source='operator_inject'`, calls `recompute_side_lots()`, resets trigger snapshots with fresh live premiums.

**Frontend:** "Inject Position" button in Positions tab header. Dialog with Active Strike / Custom Strike mode toggle, per-side active strike auto-fill, confirmation switch.

**File:** `mmm_api.py` → `inject_position()`, `MMMDashboard.js` → `MMMInjectModal`

---

### 16.2 Set Active Strike (`POST /api/mmm/session/{id}/set-active-strike`)

Switches the algo's monitoring focal point (`active_strike`) from the current strike to any other open strike (must have `active` or `shifted` status with `lots > 0`). **No order is placed** — purely a state pointer change.

**Use case:** The algo was monitoring the 71,000 CE. Operator judges the 71,800 CE (more lots, higher premium) is the better reference point. One click switches which strike the heartbeat monitors for trigger evaluation.

**Body:** `{ side: 'ce'|'pe', strike: float }`

**State changes:** Sets `session[side]['active_strike'] = strike`. Fetches live mid-prices for both the new active strike and the partner side → resets both trigger snapshots to current premiums. Without this reset the next heartbeat would compare against a stale snapshot from the old strike and potentially fire a false adjustment immediately.

**Frontend:** 📌 (PushPin) icon button on every non-active open position row in the Positions table. Single click — no confirmation dialog needed (fully reversible, no exchange order).

**File:** `mmm_api.py` → `set_active_strike()`, `MMMPositionsTable.js` → `onSetActiveStrike` prop, `mmmService.js` → `setActiveStrike()`

**WebSocket event emitted:** `mmm_active_strike_changed` `{ side, old_strike, new_strike }`

---

### 16.3 Close Strike (`POST /api/mmm/session/{id}/close-strike`)

Buys back ALL open lots at a specified strike (`active` + `shifted` statuses) with a single exchange order, then removes them from the algo ledger.

**Use case:** Market is trending and a strike is approaching ATM. Operator closes the risky near-ATM strike pro-actively, then uses Operator Inject (§16.1) to re-establish at a safer far-OTM strike. This reduces the need for perp futures delta hedging.

**Body:** `{ side: 'ce'|'pe', strike: float }`

**Guards:** Guardian GO signal, session RUNNING/PAUSED, in-flight guard (`_being_closed=True` set before order placement to prevent duplicate orders if state-removal crashes post-fill).

**State changes:**
1. Places `buy` + `reduce_only=True` order on exchange for `sum(lots)` at the strike
2. Marks all matching positions `status='closed'`, records `realized_pnl` per position
3. If closed strike was `active_strike`: auto-promotes the remaining open strike with the most lots as new `active_strike` (or sets 0 if none remain)
4. Calls `recompute_side_lots()` to rebuild derived fields
5. Resets trigger snapshots with premiums at new active strike
6. Adds to `session['total_realized_pnl']`

**Return:** `{ success, side, strike, lots_closed, fill_price, realized_pnl, new_active_strike }`

**Frontend:** 🔴 (CancelOutlined) icon button on every open position row. Confirmation dialog shows: side, strike, lots, current premium, estimated BTC cost, live `error` feedback. "Place Buyback Order" CTA.

**File:** `mmm_api.py` → `close_strike_route()`, `MMMDashboard.js` → `handleCloseStrikeRequest/Confirm + closeStrikeDlg state`, `MMMPositionsTable.js` → `onCloseStrike` prop, `mmmService.js` → `closeStrike()`

**WebSocket event emitted:** `mmm_strike_closed` `{ side, strike, lots_closed, fill_price, realized_pnl, new_active_strike }`

---

### 16.4 Operator Workflow — Close Near-ATM + Re-establish OTM

The combination of 16.3 + 16.1 replaces what would otherwise require perp futures delta hedging:

```
1. BTC trends up → CE 71,000 approaching ATM (delta risk rising)
2. Operator clicks 🔴 on CE 71,000 row → Close Strike dialog
3. Confirm → Buyback order: BUY 15 CE @ 71,000 (fills at market)
4. Position removed from ledger; algo promotes next CE strike as active
5. Operator clicks "Inject Position" → Sell 15 CE @ 73,000 (far OTM)
6. Algo registers new position, resets triggers
7. Net result: risk moved 2,000 points farther from ATM; no perp needed
```

When operator is absent, the algo handles delta risk via perp futures (§2.16) and regime controls (§2.12). When operator is present, this workflow provides a more capital-efficient alternative.

---

### 16.5 Delta Neutrality Fix — `shift_match_opposite_lots` (March 2026)

When the algo performs a strike shift (§2.5), it now optionally matches the number of new lots sold on the shifted side to equal the **opposite side's active lots**. This preserves delta neutrality at the new strike.

**Parameter:** `shift_match_opposite_lots` (bool, default `True`, hot-reloadable)

**Before:** Strike shift sold `max(original_lots, lots_to_sell)` — could produce imbalanced CE/PE lot counts after a shift, requiring immediate adjustments.

**After:** With `shift_match_opposite_lots=True`, the shifted side targets `max(opposite_active_lots, original_lots, lots_to_sell)` — so CE and PE stay balanced through shifts.

**Files:** `mmm_state.py` (DEFAULT_PARAMS + HOT_RELOAD_PARAMS), `mmm_monitor.py` (`_process_strike_shift()` + `_process_shift_fallback()`), `mmm_config.py`, `MMMSettingsDialog.js` (PARAM_RULES + UI).

---

## 17. MULTI-DTE SUPPORT (implemented March 12, 2026)

Expands MMM from 0DTE-only to multi-expiry operation (5DTE, 10DTE, 20DTE+). Core principle: 0DTE behavior is **completely untouched** — all new logic runs through v2 functions that only activate for sessions with `total_dte_hours > 36`.

### 17.1 DTE Presets (`mmm_dte_presets.py`)

Predefined parameter sets for different expiry durations:

| Preset | Interval | Wind-down Hours | Close Threshold | Max Adjustments |
|--------|----------|-----------------|-----------------|------------------|
| 0DTE | 300s (5min) | 2h | 5.0 | 20 |
| 5DTE | 900s (15min) | 6h | 3.0 | 40 |

Presets are **defaults** — user overrides always win via `apply_preset(preset_name, user_params)`.

### 17.2 Aggregate PnL Safety

Before starting a new session, the system checks combined realized + unrealized P&L across ALL active sessions:
- **OK** (<50% of `global_max_loss`): proceed
- **WARNING** (50–80%): proceed with caution
- **DANGER** (80–100%): proceed with alert
- **BLOCKED** (≥100%): new session start blocked

Default `global_max_loss` = ₹50,000. Hot-reloadable.

API: `GET /api/mmm/aggregate-pnl` returns `{safe, level, combined_pnl, global_max_loss, pct_used}`.

### 17.3 Liquidity Gate

For **fresh mode** session creation, the system fetches the option chain via `MMMInitializer.get_full_chain()` and validates liquidity near the chosen strike:
- `check_chain_liquidity(chain, strike, min_bid=1.0, min_bid_size=0.01)` → checks that both CE and PE at the nearest strike have sufficient bid and bid_size
- Blocks session creation if liquidity is insufficient

### 17.4 v2 Adaptive Interval

`compute_adaptive_interval_v2(base_interval, hours_to_expiry, total_dte_hours, enabled)` uses percentage-of-DTE tiers instead of absolute hour thresholds:

| DTE Remaining | Multiplier | Example (base=900s, 5DTE) |
|---------------|------------|---------------------------|
| > 80% | 1.5× (slow) | 1350s |
| 50–80% | 1.0× (normal) | 900s |
| 20–50% | 0.7× (faster) | 630s |
| 5–20% | 0.5× (fast) | 450s |
| < 5% | 0.3× (rapid) | 270s |

Dispatched automatically by `mmm_monitor.py` for sessions with `total_dte_hours > 36`.

### 17.5 v2 Theta Acceleration

`apply_theta_acceleration_v2(session, minutes_to_expiry, total_dte_mins)` scales the theta acceleration window proportionally:
- Window = 2% of total DTE in minutes (capped at 240 min max)
- Example: 5DTE (7200 min) → window = 144 min
- Example: 20DTE (28800 min) → window = 240 min (capped)

Compare with v1: fixed 30-minute window (appropriate for 0DTE but too small for 5DTE+).

### 17.6 v2 Near-Expiry Safety

`check_near_expiry_v2()` in `mmm_safety.py` has three tiers:
1. **Absolute thresholds** (same as v1): `auto_close_minutes_before_expiry` triggers auto-close, `stop_adjustments_minutes_before_expiry` stops new adjustments
2. **Wind-down zone**: preset's `wind_down_hours_before_expiry` triggers wind-down mode
3. **Percentage early warning**: last 5% of total DTE triggers a warning alert

Dispatched automatically for sessions with `total_dte_hours > 36 && dte_category != '0DTE'`.

### 17.7 Frontend Changes

- **CreateSessionDialog:** DTE Preset dropdown fetches from `/api/mmm/dte-presets`, auto-fills form fields on preset selection
- **Session cards:** DTE category Chip displayed next to session ID (only for non-0DTE sessions, e.g., "5DTE")
- **Header:** Changed from "BTC 0DTE" badge to "BTC Options"
- **mmmService.js:** Added `getDTEPresets()` and `getAggregatePnL()` API calls

### 17.8 State & Config Changes

**New DEFAULT_PARAMS:** `dte_category` (str), `total_dte_hours` (float), `global_max_loss` (float, ₹50,000)

**New HOT_RELOAD_PARAMS:** `global_max_loss`

**New PARAM_RULES:** `dte_category` (str, not hot), `total_dte_hours` (float [0, 10000], not hot), `global_max_loss` (float [100, 1e9], hot)

**Session creation flow:**
1. User selects DTE preset in dialog → auto-fills params
2. `create_session()` calls `apply_preset()` to merge preset defaults with user overrides
3. `compute_total_dte_hours()` calculates hours to expiry and stores in `total_dte_hours`
4. `infer_dte_category()` infers category from DTE hours if not explicitly set
5. Aggregate PnL check runs before session start (blocks if combined loss ≥ `global_max_loss`)
6. Liquidity gate check runs for fresh-mode sessions

### 17.9 v1 vs v2 Dispatch Summary

| Component | v1 (0DTE) | v2 (multi-DTE) | Dispatch condition |
|-----------|-----------|----------------|--------------------|
| Adaptive interval | Absolute hour tiers | % of DTE tiers | `total_dte_hours > 36 && dte_category != '0DTE'` |
| Theta acceleration | Fixed 30-min window | 2% of total DTE (max 240 min) | Same |
| Near-expiry safety | Absolute minutes | 3-tier (absolute + wind-down + % warning) | Same |
| All other modules | Unchanged | Unchanged | N/A |

---

## 18. TRADE TRANSPARENCY SYSTEM (2026-03-18)

Institutional-grade write-once audit trail. Every confirmed fill and every operational state change is persisted to SQLite. **Does not affect trading logic — all writes are fire-and-forget.**

### 18.1 Files

| File | Role |
|---|---|
| `mmm_audit_log.py` | `MMMTradeAuditLog` + `MMMSessionEventLog` — queue-based WAL SQLite writer. Singletons: `get_audit_log()`, `get_event_log()` |
| `mmm_audit_remark.py` | `build_trade_remark(**kwargs) → str`, `build_event_remark(category, type, **ctx) → str` — zero deps, never raises |
| `mmm_audit_reconciler.py` | `reconcile_session(session_id, session) → dict` — compares audit sums vs live session state |

### 18.2 Tables (in `mmm_sessions.db`)

**`position_audit_log`** — one row per confirmed exchange fill:
- `action` TEXT — `BUY` or `SELL`
- `option_type` TEXT — `CE`, `PE`, or `PERP`
- `strike`, `quantity_requested`, `quantity_filled`, `premium`
- `event_type` TEXT — `ENTRY | ADJUSTMENT | REVERSAL | CLOSE | WIND_DOWN | EXIT | RECYCLE_BUY | RECYCLE_SELL | PERP_HEDGE`
- `mechanism` TEXT — `fresh_entry | import | harvest | close_at_5 | recycler | atm_shield | wind_down | emergency | operator | perp_hedge | perp_close`
- `realized_pnl_usd` REAL — stored at close time; NULL for open sells
- `idempotency_key` TEXT UNIQUE — prevents duplicate rows on crash/restart
- `remark` TEXT — human-readable trader-facing description

**`session_event_log`** — one row per operational state change:
- `event_category` TEXT — `SESSION_LIFECYCLE | SAFETY | REGIME | MARGIN | PARAM_CHANGE | STRIKE_SHIFT`
- `event_type` TEXT — subcategory (e.g. `started`, `tier_change`, `transition`, `hot_reload`, `shifted`)
- `severity` TEXT — `INFO | WARN | CRITICAL`
- `remark` TEXT, `details` JSON

### 18.3 Write Rules (NEVER violate)

```python
# Pattern: always after success confirmed, always wrapped
try:
    get_audit_log().enqueue_trade(
        session_id=sid, action='SELL', option_type='CE',
        strike=strike, quantity_requested=lots, quantity_filled=filled_lots,
        premium=fill_price, event_type='ENTRY', mechanism='fresh_entry',
        realized_pnl_usd=None, remark=build_trade_remark(...),
    )
except Exception:
    pass
```

- **Only call after `result.get('success') == True`** — never on failure
- **Always `try/except: pass`** — audit failure must never abort trading
- **All P&L in USD** — no INR conversion in audit layer
- **No UPDATE/DELETE ever** — INSERT OR IGNORE only
- `realized_pnl_usd`: pass for BUY rows (closing fills); None/omit for SELL rows (opens)
- `closing_entry_premium` + `closing_entry_lots`: pass for buybacks so P&L auto-computes if not provided

### 18.4 Instrumented Paths

| File | What is recorded |
|---|---|
| `mmm_api.py` | Mode A entry (CE+PE SELL ENTRY), Mode B import (CE+PE SELL ENTRY), operator inject (SELL ENTRY), operator close-strike (BUY EXIT), session started/stopped events |
| `mmm_engine.py` | `execute_adjustment()` — SELL ADJUSTMENT / REVERSAL / RECYCLE_SELL |
| `mmm_close_at_5.py` | `close_position()` — BUY CLOSE / EXIT / RECYCLE_BUY / WIND_DOWN for all mechanisms |
| `mmm_monitor.py` | Wind-down LIFO buybacks (separate path from close_position), regime transition events, SAFETY critical events, session completed event |
| `mmm_perp_hedge.py` | `run_perp_hedge()` + `close_all_perp()` — BUY/SELL PERP_HEDGE |
| `mmm_margin_guardian.py` | Margin tier change events |
| `mmm_strike_shift.py` | Strike shift events (post `activate_new_strike()`) |
| `mmm_api.py` (params) | PARAM_CHANGE event per hot-reload param changed |

### 18.5 Read API (REST — never in heartbeat)

```
GET /api/mmm/session/<id>/audit/trades          → {rows: [...], count, page, limit}
GET /api/mmm/session/<id>/audit/strike_summary  → {summary: [...]}
GET /api/mmm/session/<id>/audit/pnl             → {total_realized_pnl_usd, ce_realized_pnl_usd, pe_realized_pnl_usd, ...}
GET /api/mmm/session/<id>/audit/events          → {events: [...], count}
GET /api/mmm/session/<id>/audit/reconcile       → {is_clean, pnl_ok, pnl_delta, pnl_audit, pnl_session, position_discrepancies, trade_count}
```

`reconcile` always returns HTTP 200. Check `is_clean` in body. `trade_count=0` means session predates audit deployment (not an error).

### 18.6 Frontend

`MMMTradeAuditPanel.js` — tab 16 in `MMMDashboard.js` SessionDetail. Sub-tabs: Fills | Strike Summary | P&L Attribution | Events | Reconcile. Auto-reconcile banner fires on panel mount only when `is_clean=false AND trade_count > 0`.

