# MMM User Guide — Money Mind & Method Algorithm

> **Audience:** Traders running the MMM BTC options bot via the WebUI.
> **Last Updated:** March 12, 2026
> **Exchange:** Delta Exchange India | **Instrument:** BTC 0DTE / weekly options
> **Lot Size:** 0.001 BTC per lot

---

## Table of Contents

1. [What MMM Does](#1-what-mmm-does)
2. [Quick Start — New Session](#2-quick-start--new-session)
3. [Understanding the Dashboard](#3-understanding-the-dashboard)
4. [Exact Heartbeat Logic Flow](#4-exact-heartbeat-logic-flow)
5. [Key Parameters Explained](#5-key-parameters-explained)
6. [Safety Systems](#6-safety-systems)
7. [Regime Controls](#7-regime-controls)
8. [Adjustment Engine — How Lots Are Calculated](#8-adjustment-engine--how-lots-are-calculated)
9. [Lot Lifecycle (M1 / M2 / M3)](#9-lot-lifecycle-m1--m2--m3)
10. [Strike Shift & Proactive Shift](#10-strike-shift--proactive-shift)
11. [Close-at-5 & Wind-Down](#11-close-at-5--wind-down)
12. [ATM Shield — Proactive Close & Retreat](#12-atm-shield--proactive-close--retreat)
13. [Margin Guardian](#13-margin-guardian)
14. [Perpetual Futures Delta Hedge](#14-perpetual-futures-delta-hedge)
15. [Whipsaw Protection (Graduated)](#15-whipsaw-protection-graduated)
16. [Lot Velocity Limiter](#16-lot-velocity-limiter)
17. [Advanced: Split Ledger](#17-advanced-split-ledger)
18. [Settings Hot-Reload](#18-settings-hot-reload)
19. [Common Scenarios & What to Do](#19-common-scenarios--what-to-do)
20. [Parameters Reference Table](#20-parameters-reference-table)

---

## 1. What MMM Does

MMM is a **premium decay harvesting strategy** on BTC 0DTE options. In plain terms:

```
START: Sell CE at strike above spot + Sell PE at strike below spot
       Collect premium from both sides.

WHEN ONE SIDE RISES: BTC moved → that option is now worth more.
       Sell more of the OTHER side (which is now far OTM and cheap → decaying fast)
       to collect enough premium to offset the losing side.

WHEN PREMIUM DECAYS TO ≤5: Close that position, locking in profit.

SHIFT STRIKE: When a side's premium decays below shift_threshold,
       move to a fresh OTM strike to collect more premium.
```

**P&L sources:**
- Premium decay on open positions (time value erosion)
- Realized P&L when positions are bought back at close-at-5
- M1 Harvest: proactive buyback of frozen positions that decayed to profit levels
- M2 Recycle: swap near-worthless frozen lots for new higher-premium positions

**Risk:** The algo adds lots as BTC moves. A strong directional move accelerates losses until close-at-5 closes out the underwater side.

---

## 2. Quick Start — New Session

### Step 1: Configure Parameters

Navigate to **MMM → New Session** in the WebUI. Required fields:

| Field | Description | Example |
|---|---|---|
| **Expiry** | Contract expiry date (DDMMYYYY) | `10032026` |
| **Desired CE Premium** | Target premium for call sell | `100` USD |
| **Desired PE Premium** | Target premium for put sell | `100` USD |
| **Initial Lots** | Starting lots each side | `10` |

Click **Find Strikes** — the algo scans the options chain and shows the best OTM strikes near your target premium.

### Step 2: Review and Confirm

The system shows:
- Proposed CE strike + current premium
- Proposed PE strike + current premium
- Estimated initial premium collected

Click **Confirm & Start** to place the sell orders and begin the heartbeat loop.

### Step 3: Monitor

The dashboard updates every heartbeat (adaptive: 60–1200 seconds). Key things to watch:
- **CE / PE premium** vs their trigger snapshots
- **Total P&L** (realized + unrealized)
- **Lots**: active lots per side
- **Regime** status: NORMAL / ELEVATED / HIGH / BLOCKED

---

## 3. Understanding the Dashboard

### P&L Panel

```
Total P&L = Realized P&L + Unrealized P&L − Total Fees + Perp Hedge P&L

Unrealized P&L = Σ [(entry_price − current_price) × lots × 0.001 BTC]
                 for all open positions (active + frozen)

Realized P&L = Sum of all closed positions' P&L
```

### Position States

| State | Meaning |
|---|---|
| **Active** | Currently open at the active strike. Counted against `max_lots_per_side` cap. |
| **Frozen** | At a prior strike after a shift. Still open on the exchange, still accruing P&L. Counted only against `max_total_exposure`. |
| **Shifted** | Same as frozen — the position was "shifted" when the algo moved to a new strike. |
| **Closed** | Bought back via close-at-5, M1 harvest, or M2 recycle. No longer on exchange. |

**Important:** "Frozen" does NOT mean closed or safe. Frozen positions are live risk on the exchange and are included in ALL loss calculations.

### Heartbeat Status

| Status | Meaning |
|---|---|
| Running | Normal — heartbeat firing as expected |
| Paused | Max adjustments hit, whipsaw detected, or max loss approaching |
| Stopped | Session ended — manually, by safety, or both-sides-closed |
| Partial Beat | Exchange unreachable — running safety checks with cached prices |
| Miss Beat | No cached prices available — heartbeat skipped entirely |

---

## 4. Exact Heartbeat Logic Flow

This is the exact step-by-step sequence that runs every heartbeat. Understanding this flow is critical for knowing why the algo did (or didn't) take an action.

```
┌─────────────────────────────────────────────────────────┐
│                    HEARTBEAT START                       │
│  (runs every adjustment_interval seconds, adaptive)     │
└───────────────┬─────────────────────────────────────────┘
                │
    ┌───────────▼───────────┐
    │  STEP 0: RELOAD       │
    │  Load session from    │  ← Hot-reload picks up param changes
    │  storage + backfill   │
    │  new DEFAULT_PARAMS   │
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │  STEP 0: RECOMPUTE    │
    │  recompute_side_lots  │  ← Rebuilds active_lots, frozen_lots,
    │  for CE and PE        │     total_lots from positions[] ledger
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │  STEP 0: RECONCILE    │  ← Compare internal state vs exchange
    │  Exchange positions   │     reality. Log warnings if mismatch.
    │  (skipped when PAUSED)│
    └───────────┬───────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 0.5: MARGIN CHECK   │
    │  MarginGuardian.check()   │
    │                           │
    │  ┌─ GREEN → continue      │
    │  ├─ YELLOW → set          │  ← _margin_block_sells flag
    │  │   _margin_block_sells  │
    │  ├─ ORANGE → set          │  ← _margin_wind_down flag
    │  │   _margin_wind_down    │
    │  ├─ RED → emergency       │  ← Close positions, return early
    │  │   close + return       │
    │  ├─ CRITICAL → survival   │  ← Close ALL, return early
    │  │   close + return       │
    │  └─ 3× CRITICAL →        │  ← Force stop session entirely
    │     force_stop_session    │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────┐
    │  STEP 1: FETCH        │
    │  PREMIUMS             │
    │                       │
    │  Fetch CE mark price  │  ← From Delta Exchange API
    │  Fetch PE mark price  │
    │                       │
    │  If BOTH fail:        │
    │    → Use cached prices│
    │    → Run close-at-5   │
    │    → Run safety       │
    │    → Record as MISS   │
    │      or PARTIAL beat  │
    │    → RETURN early     │
    └───────────┬───────────┘
                │
    ┌───────────▼───────────────┐
    │  TRIGGER SNAPSHOT HEAL    │
    │  If active_strike has no  │  ← Prevents 0.0 baseline
    │  trigger snapshot, set it │     from blocking triggers
    │  to current premium       │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  ATM CHECKS               │
    │  wind_down_on_atm:        │  ← If spot within 0.5% of active
    │    → activate wind-down   │     strike, switch to wind-down
    │  close_at_atm:            │  ← If spot within 0.5% of active
    │    → emergency close ALL  │     strike, close everything
    │  ATM Shield deferral:     │  ← If shield has capacity, let
    │    → defer to Step 5.5    │     shield handle instead
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 1.5: PROACTIVE      │
    │  SHIFT SCANNER            │
    │  For each side:           │
    │    If premium < shift     │  ← Shift BEFORE close-at-5 can
    │    threshold AND has      │     eat the positions
    │    active lots →          │
    │    trigger shift now      │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 2: CLOSE-AT-5       │
    │  Scan ALL positions       │
    │  (active + frozen)        │
    │  If bid ≤ close_at        │  ← Uses BID price, not mark
    │  threshold → buy back     │
    │  Lock in realized P&L     │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 2.1: M1 HARVEST     │
    │  (only if NOT in          │
    │   wind-down mode)         │
    │  Scan frozen positions    │
    │  for profitable buybacks  │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  CHECK: BOTH SIDES CLOSED │
    │  If CE lots=0 AND PE      │  ← Strategy complete!
    │  lots=0 → stop session    │     Close perp hedge first
    │                           │
    │  CHECK: ONE SIDE CLOSED   │
    │  If CE=0 but PE>0 (or     │  ← Unhedged exposure!
    │  vice versa) → PAUSE      │     Operator must intervene
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  COMPUTE UNREALIZED P&L   │
    │  For ALL positions        │  ← Fresh P&L for safety checks
    │  (active + frozen)        │
    │  If >50% fetches fail     │
    │  → PAUSE (data unreliable)│
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 3: SAFETY CHECKS    │
    │  Run all 12 checks:       │
    │  1. Position cap          │
    │  2. Total exposure        │
    │  3. Max adjustments       │
    │  4. Max loss (hard stop)  │
    │  5. Max loss sizing       │
    │  6. Whipsaw (graduated)   │
    │  7. Asymmetry (3:1/5:1/7:1)
    │  8. Near expiry           │
    │  9. P&L guardrail         │
    │  10. Margin (proxy)       │
    │  11. Lot velocity         │
    │  12. Trailing stop        │
    │                           │
    │  Actions:                 │
    │  → auto_close: close ALL  │
    │  → stop: stop session     │
    │  → stop_adjustments:      │
    │    skip to P&L (no sells) │
    │  → pause: pause session   │
    │  → resume: auto-resume    │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 3.5: REGIME         │
    │  CONTROLS                 │
    │  (only if regime_enabled) │
    │                           │
    │  A. Vol Regime:           │
    │     IV change + RV →      │
    │     NORMAL/ELEVATED/HIGH  │
    │                           │
    │  B. Gamma Cap:            │
    │     Dollar gamma →        │
    │     SOFT/HARD/EMERGENCY   │
    │                           │
    │  C. Trend Guard:          │
    │     Spot % move →         │
    │     TIER 0/1/2/3/4        │
    │                           │
    │  Aggregate action:        │
    │  NORMAL → proceed         │
    │  WARN → proceed with log  │
    │  BLOCK_CE/PE → block side │
    │  BLOCK_ALL → block sells  │
    │  FORCE_REDUCE → PAUSE     │
    │  PAUSE → pause session    │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 4: TRIGGER          │
    │  EVALUATION               │
    │  (skipped if safety or    │
    │   regime blocked above)   │
    │                           │
    │  For each side:           │
    │  excess = (now - snap) /  │
    │           snap × 100      │
    │  If excess > min_trigger  │
    │  _move → TRIGGERED        │
    │                           │
    │  Outcomes:                │
    │  A. NONE → no action      │
    │  B. CE only → adjust CE   │
    │  C. PE only → adjust PE   │
    │  D. BOTH → alert operator │
    └───────────┬───────────────┘
                │
         ┌──────┴──────┐
    Outcome A      Outcomes B/C/D
    (NONE)         (TRIGGERED)
         │              │
         │    ┌─────────▼─────────────┐
         │    │  STEP 4.5: PRE-       │
         │    │  ADJUSTMENT GATES     │
         │    │                       │
         │    │  Whipsaw cooldown?    │
         │    │  Consecutive same-    │
         │    │  direction limit?     │
         │    │  Margin blocks sells? │
         │    │  Regime blocks sells? │
         │    │  Lot velocity limit?  │
         │    │                       │
         │    │  If any gate blocks → │
         │    │  skip adjustment      │
         │    └─────────┬─────────────┘
         │              │
         │    ┌─────────▼─────────────┐
         │    │  STEP 5: REVERSAL     │
         │    │  CHECK                │
         │    │                       │
         │    │  Did aggressor side   │
         │    │  change? (CE→PE or    │
         │    │  PE→CE)               │
         │    │                       │
         │    │  If YES:              │
         │    │  → Record reversal    │
         │    │  → Activate cooldown  │
         │    │  → Use Case B formula │
         │    │    (reversal P&L)     │
         │    │                       │
         │    │  If skipped (P&L>0):  │
         │    │  → Update triggers    │
         │    │  → Don't sell         │
         │    └─────────┬─────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  IS WIND-DOWN ACTIVE?          │
         │    │                                │
         │    │  YES → LIFO BUYBACK            │
         │    │  Buy back newest frozen lots   │
         │    │  (25% per trigger, LIFO order) │
         │    │  DO NOT sell more              │
         │    │                                │
         │    │  NO → ADJUSTMENT (SELL MORE)   │
         │    │  Go to Step 5.1                │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.1: STRIKE SHIFT       │
         │    │  CHECK                         │
         │    │                                │
         │    │  If hedge side premium <        │
         │    │  shift_threshold → shift:       │
         │    │  1. Freeze current positions    │
         │    │  2. Find new OTM strike         │
         │    │  3. Clear old trigger snapshot   │
         │    │  4. Activate new strike          │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.2: LOT CALCULATION    │
         │    │                                │
         │    │  Case A (standard):            │
         │    │  total_loss = active_loss +     │
         │    │    ALL frozen position losses   │
         │    │  lots = loss / hedge_premium    │
         │    │    × (1 + premium_buffer_pct)   │
         │    │                                │
         │    │  Case B (reversal):            │
         │    │  total_loss = actual P&L of     │
         │    │    all adjustment fills          │
         │    │                                │
         │    │  Modifiers applied:             │
         │    │  • Gamma-aware multiplier       │
         │    │  • Trend boost (if IMP-2)       │
         │    │  • Asymmetry reduction (IMP-3)  │
         │    │  • OTM scaling (IMP-4)          │
         │    │  • Position cap enforcement     │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.3: M2 RECYCLING       │
         │    │  (only if position cap hit)     │
         │    │                                │
         │    │  Phase A: Buy back cheap frozen │
         │    │  Phase B: Sell at better strike │
         │    │  Rollback Phase A if B fails    │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.4: EXECUTE ORDER      │
         │    │                                │
         │    │  smart_execute():              │
         │    │  1. Get L2 orderbook            │
         │    │  2. Place limit at mid-price    │
         │    │  3. Wait 60s for fill           │
         │    │  4. If not filled → reprice     │
         │    │     (up to 4 attempts)          │
         │    │  5. Attempt 3-4: use best_bid   │
         │    │  6. Cancel if all fail          │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.5: ATM SHIELD         │
         │    │  (if enabled + spot near       │
         │    │   active strike)               │
         │    │                                │
         │    │  1. Close ALL active on        │
         │    │     endangered side             │
         │    │  2. Find new OTM strike         │
         │    │  3. Re-sell with recovery lots  │
         │    │  4. Sympathetic rebalance       │
         │    │     safe side if needed         │
         │    └─────────┬─────────────────────┘
         │              │
         │    ┌─────────▼─────────────────────┐
         │    │  STEP 5.6: FSU SCALE-UP       │
         │    │  (if eligible: P&L>0, margin   │
         │    │   green, regime OK, both sides │
         │    │   decayed)                      │
         │    │                                │
         │    │  Find fresh strikes + sell     │
         │    │  scale_lots_pct × initial_lots │
         │    └─────────┬─────────────────────┘
         │              │
    ┌────┴──────────────▼─────────────────────┐
    │  STEP 6: UPDATE STATE                    │
    │                                          │
    │  • Update trigger snapshots              │
    │  • Record adjustment in positions[]      │
    │  • Update active_lots, total_lots        │
    │  • Increment adjustment_count            │
    │  • Record fill in adjustment_fills[]     │
    └───────────┬──────────────────────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 7: RECONCILIATION   │
    │  (every 5 adjustments)    │
    │  Compare tracked P&L vs   │
    │  computed P&L. Log warning │
    │  if drift > 5%            │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 7.5: PERP HEDGE     │
    │  (if perp_hedge_enabled)  │
    │                           │
    │  Compute portfolio delta  │
    │  + projected delta from   │
    │  adjustment just made     │
    │                           │
    │  If |delta| > threshold   │
    │  → place perp order       │
    │  (with flip rate limit)   │
    └───────────┬───────────────┘
                │
    ┌───────────▼───────────────┐
    │  STEP 8: FINALIZE         │
    │                           │
    │  • Compute total P&L      │
    │  • Update peak P&L        │
    │    (with 15-min half-life │
    │     decay)                │
    │  • Emit WebSocket         │
    │    heartbeat event        │
    │  • Save session to        │
    │    storage                │
    │  • Record health beat     │
    │  • Wait for next interval │
    └───────────────────────────┘
```

### Interval Layers (From Longest to Shortest)

The heartbeat interval is determined by three layers, each can only make it shorter:

1. **Base Interval:** `adjustment_interval` (default 300s = 5 min)
2. **Adaptive Scaling:** Based on hours-to-expiry:
   - > 8 hours: base × 1.5 (longer, less frequent)
   - 4-8 hours: base × 1.0 (normal)
   - 2-4 hours: base × 0.7 (faster)
   - 1-2 hours: base × 0.5
   - < 1 hour: base × 0.3 (rapid)
3. **Theta Acceleration:** In last 30 minutes, further shortens interval and widens trigger sensitivity
4. **Margin Rapid Check:** If margin YELLOW+, shrinks to 15s

---

## 5. Key Parameters Explained

### Adjustment Trigger

```
trigger_snapshot = premium at the moment the LAST adjustment on this side happened
                  (or entry price if no adjustments yet)

excess_pct = (current_premium − trigger_snapshot) / max(trigger_snapshot, 1.0) × 100

triggered = excess_pct > min_trigger_move (%)
```

**`min_trigger_move`** (default: 10%) — how much the premium must rise above its snapshot level before the algo reacts. This is percentage-based (not absolute dollar amount) so it works the same at $5 premium and $500 premium.

### Shift Threshold

**`shift_threshold`** (default: 50 USD) — if premium falls below this, a strike shift is triggered.

The actual threshold is dynamic: `max(shift_threshold, initial_hedge_premium × shift_threshold_pct)`. This prevents the threshold from collapsing after multiple shifts.

### Close-at-5

**`close_at_threshold`** (default: 5 USD) — any position with **bid price** ≤ this is bought back (position closed, profit locked). Uses bid price (not mark) because bid reflects the actual cost to buy back.

### Max Loss

**`max_loss_amount`** (default: 5000 USD) — if total P&L (including perp hedge P&L) falls to −this value, ALL positions are automatically closed. This is a hard stop — no override.

### Trailing Stop

**`trailing_stop_pct`** (default: 0 = disabled) — once P&L peaks, if it drops below `peak × trailing_stop_pct`, adjustments are blocked. Peak decays with a 15-minute half-life to prevent permanent lockout.

---

## 6. Safety Systems

MMM has 12 safety checks that run every heartbeat BEFORE any adjustment:

| # | Check | What It Catches | Action |
|---|---|---|---|
| 1 | **Position Cap** | `active_lots ≥ max_lots_per_side` | Block sells on that side + trigger M2 |
| 2 | **Total Exposure** | `active + frozen ≥ max_total_exposure` | Block sells (warn) |
| 3 | **Max Adjustments** | `adjustment_count ≥ max_adjustments` | Pause session (auto-resume if limit raised) |
| 4 | **Max Loss** | `total_pnl ≤ −max_loss_amount` | Auto-close ALL positions |
| 5 | **Max Loss Sizing** | `max_loss_amount` too small for position size | Warning (one-time) |
| 6 | **Whipsaw** | Rapid CE↔PE alternation (graduated score) | CAUTION → RESTRICT → COOLDOWN |
| 7 | **Asymmetry** | CE/PE imbalance: 3:1 warn, 5:1 reduce, 7:1 block | Progressive action |
| 8 | **Near Expiry** | Close to `stop_adjustment_mins` or `auto_close_mins` | Stop adjustments / auto-close |
| 9 | **P&L Guardrail** | P&L at 50%/80%/100% of max_loss | Warning → Alert → Stop |
| 10 | **Margin (Proxy)** | Combined lots > `max_lots × 1.5` | Warning |
| 11 | **Lot Velocity** | Too many lots sold in rolling window | Block sells |
| 12 | **Trailing Stop** | P&L fell below `peak × trailing_stop_pct` | Block adjustments |

**Priority order when multiple fire:** auto_close > stop > stop_adjustments > pause > warn

---

## 7. Regime Controls

Regime controls are **pre-adjustment risk intelligence** — they block or reduce adjustments when market conditions are unfavorable. All guarded by master switch `regime_enabled` (default: **disabled** until you opt in).

When disabled, regime data is still computed and shown in the UI (observation mode) but never blocks anything.

### A. Volatility Regime

Monitors IV change rate (60% weight) and realized volatility (40% weight).

**Composite score:** `r_score = 0.6 × (|IV_change| / threshold) + 0.4 × (RV / threshold)`

| Tier | Score | Action |
|---|---|---|
| NORMAL | < 0.70 | No effect |
| ELEVATED | 0.70–0.99 | Warning |
| HIGH | ≥ 1.00 | Configurable: `block_sells` / `pause` / `wind_down` |

**Cooldown:** After HIGH, must stay below threshold for 10 consecutive beats before resetting to NORMAL.

### B. Gamma Cap

Estimates portfolio dollar gamma: `$Gamma = |portfolio_gamma| × spot^2 × 0.01`

This represents the P&L impact of a 1% spot move.

| Level | Default | Action |
|---|---|---|
| Soft limit | $2,500 | Warning |
| Hard limit | $5,000 | Block new sells |
| Emergency | $10,000 | Pause session (manual review) |

**Near-expiry multiplier:** In last 30 minutes, all limits tightened by 0.5× (gamma explodes near ATM at expiry).

### C. Trend Guard (4-Tier Graduated Response)

Detects BTC spot directional momentum using % move from anchor, max excursion, and EMA slope.

| Tier | Spot Move from Anchor | Effect |
|---|---|---|
| 0 (None) | < `trend_tier1_pct` | Normal |
| 1 (Alert) | ≥ `trend_tier1_pct` | Lots reduced by `trend_tier1_lot_reduction` (default 30%) |
| 2 (Guard) | ≥ `trend_tier2_pct` | Block sells on aggressor side only |
| 3 (Block) | ≥ `trend_tier3_pct` | Block ALL sells |
| 4 (Wind-Down) | ≥ `trend_tier4_pct` | Auto-trigger wind-down mode |

**Important:** Tiers only escalate during a trend — they never de-escalate until the trend reverses.

**Reset conditions:**
1. Price crosses anchor (direction reversal)
2. Sufficient retracement + N calm beats (default 5)
3. Direction flip + EMA slope flip

### D. Aggregate Action (Priority Order)

When multiple regime signals fire, the highest priority wins:

1. Gamma emergency → `FORCE_REDUCE` (pause session)
2. Vol HIGH + any trend → `BLOCK_ALL_SELLS`
3. Vol HIGH alone → action from config
4. Gamma hard → `BLOCK_ALL_SELLS`
5. Trend tiers (escalating blocks)
6. Gamma soft → `WARN`

---

## 8. Adjustment Engine — How Lots Are Calculated

### Case A: Standard Adjustment (Same Aggressor)

```
Step 1: Compute total loss
  active_loss = (active_premium_now - entry_premium) × active_lots × 0.001 BTC
  frozen_loss = Σ (frozen_premium_now - frozen_entry) × frozen_lots × 0.001 BTC
  total_loss = active_loss + frozen_loss    ← ALL positions, never exclude any

Step 2: Calculate base lots
  base_lots = |total_loss| / (hedge_premium × 0.001 BTC)

Step 3: Add premium buffer
  lots_with_buffer = base_lots × (1 + premium_buffer_pct)    ← default +5%

Step 4: Apply modifiers
  × gamma_aware_multiplier (1.0–1.3×)   if premium spiked hard
  × trend_boost (1.3–2.0×)              if IMP-2 enabled + safe side
  × asymmetry_reduction (0.5×)          if 5:1 imbalance (IMP-3)
  × otm_scaling (1.0–2.0×)             if new strike far from spot (IMP-4)

Step 5: Apply caps
  lots = min(lots, max_lots_per_side - active_lots)
  lots = min(lots, max_total_exposure - total_lots)
  lots = max(lots, 1)                    ← always sell at least 1 lot
```

### Case B: Reversal Adjustment (Aggressor Changed)

```
Step 1: Compute reversal loss
  For each prior adjustment fill on the OLD aggressor side:
    fill_pnl = (fill_entry_price - current_price) × fill_lots × 0.001 BTC
  total_reversal_loss = Σ fill_pnl for all fills where pnl < 0

Step 2-5: Same as Case A using reversal_loss instead of standard loss
```

---

## 9. Lot Lifecycle (M1 / M2 / M3)

### M1 — Profit Harvesting

Every heartbeat (except during wind-down), MMM scans frozen positions. A position is eligible if:
- Premium has decayed ≥ `harvest_profit_pct`% (default 40%) from entry
- Position has been frozen ≥ `harvest_min_age_mins` (default 30 minutes)
- Capacity pressure ≥ `harvest_pressure_threshold` (default 60%)

Harvested positions are bought back via the same `close_position()` used by close-at-5.

### M2 — Lot Recycling (Emergency Capacity Relief)

Triggered only when `calculate_lots_to_sell()` returns `is_position_cap = True`.

**Phase A:** Select cheapest frozen positions. Buy them back (cheapest first).
**Viability Check:** New premium must be ≥ 2.5× average recycle premium AND net lot gain ≥ 5.
**Phase B:** Sell at new strike with computed lot count.
**Rollback:** If Phase B fails, Phase A buybacks are reversed (positions restored to active state, realized P&L rolled back).

**Cooldown:** 300 seconds between recycle attempts.

### M3 — Asymmetry Rebalancing

During M1 harvesting, if one side has `rebalance_asymmetry_threshold`× more lots than the other:
- The heavy side's harvest threshold is relaxed (40% → 20-30%)
- This preferentially closes positions on the over-loaded side

If the other side has ZERO lots (worst asymmetry), M3 boosts to extreme relaxation levels.

---

## 10. Strike Shift & Proactive Shift

### Normal Strike Shift

Triggered when hedge side premium < `shift_threshold`:

1. **Check shift needed:** `max(shift_threshold, initial_premium × shift_threshold_pct)`
2. **Preserve initial premium:** Stored as `_initial_hedge_premium` to prevent threshold collapse
3. **Freeze current positions:** Mark all active positions as 'shifted' status
4. **Clear old trigger snapshot:** Prevent re-hedging at stale strike
5. **Find new strike:** Scan chain for OTM strike closest to `shift_target_premium`
6. **Activate new strike:** Create new position in unified ledger
7. **Shift-time recycle:** Optionally close cheap frozen positions during shift

### Proactive Shift Scanner

Runs BEFORE close-at-5 (Step 1.5). For each side:
- If premium is between `close_at_threshold` and `shift_threshold`
- AND the side has active lots
- → Trigger shift immediately (don't wait for opposite side trigger)

This prevents premium decaying all the way to $5 before the algo reacts.

Enable/disable: `proactive_shift_enabled` (default: `True`).

**Note:** There is currently no cooldown between shifts — this can cause rapid oscillation in choppy markets (see audit report CONFLICT-7).

---

## 11. Close-at-5 & Wind-Down

### Close-at-5

Every heartbeat, all positions (active AND frozen) are scanned. Any position with `bid_price ≤ close_at_threshold` is bought back.

**In-flight guard:** Before placing a buyback order, the position is marked `_being_closed = True` to prevent duplicate orders if the heartbeat runs again before the order fills.

**Execution:** Uses `smart_execute()` with up to 4 reprice attempts. If all fail, marks position as not being closed and retries next heartbeat.

### Wind-Down Mode

Activated by any of:
- `wind_down_enabled = True` (manual toggle)
- `wind_down_on_atm = True` AND spot hits active strike (ATM trigger)
- Regime TREND_TIER_4 (auto-trigger)
- `wind_down_hours_before_expiry` (time-based)

**How it works:**
- When triggered, INSTEAD of selling more lots, the algo REDUCES positions
- Uses LIFO order: newest adjustment fills bought back first, original lots last
- Buyback fraction: `wind_down_buyback_pct` (default 25%) of available lots per trigger
- Close threshold elevated to `wind_down_close_threshold` (default 20 USD)
- Atomic rollback: deep-copies positions before modification, restores on error

### Auto-Close (End of Day)

At `auto_close_mins` before expiry (default: 5 minutes), ALL remaining positions are closed using emergency execution (IOC orders, taker fills accepted, 2 attempts × 10s timeout).

---

## 12. ATM Shield — Proactive Close & Retreat

When spot price approaches the active strike, ATM Shield proactively closes and re-positions before losses accelerate.

**Enable:** `atm_shield_enabled = True`

### Gate Checks (All Must Pass)

1. Shield enabled
2. Session status = RUNNING
3. Margin tier < RED
4. Not in auto-close window
5. Cooldown elapsed since last fire
6. Fires remaining < `atm_shield_max_per_session` (default 3)

### Execution Flow

1. **Close ALL active positions** on endangered side via `close_position()`
2. **Find new OTM strike** with minimum distance from spot
3. **Re-sell endangered side:** base lots + recovery lots (30% of loss by default)
4. **Sympathetic rebalance:** If safe side premium decayed, shift it too
5. **Update state:** Record fire count, emit activity + WebSocket

### Dynamic Proximity

The trigger threshold widens as expiry approaches:
```
effective_threshold = atm_shield_proximity_pct × time_multiplier
time_multiplier = max(1.0, min(3.0, 3.0 / hours_to_expiry))
```
In the last hour, the threshold is 3× wider (ATM is more dangerous near expiry).

---

## 13. Margin Guardian

Real-time margin utilization monitoring from Delta Exchange.

**Enable:** `margin_monitor_enabled = True`

### Tier Thresholds (default values)

| Tier | Utilization | Action |
|---|---|---|
| GREEN | < 50% | Normal — no restrictions |
| YELLOW | 50–60% | Block ALL new sells |
| ORANGE | 60–75% | Block sells + activate wind-down |
| RED | 75–85% | Emergency reduce — taker orders, close positions |
| CRITICAL | > 85% | Survival — close ALL, stop session |

**Consecutive CRITICAL escalation:** After 3 consecutive heartbeats at CRITICAL, the session is force-stopped.

**Rapid check mode:** When YELLOW+, heartbeat interval shrinks to 15s for faster response.

### Margin Computation

```
utilization% = total_margin_used / net_equity × 100

total_margin_used = priority chain:
  1. portfolio_margin (if available)
  2. blocked_margin (if available)
  3. position_margin + order_margin + cross_margin (fallback)

net_equity = meta.net_equity (includes unrealized P&L)
           or balance (fallback)
```

---

## 14. Perpetual Futures Delta Hedge

Optional delta neutralization via BTC perpetual futures.

**Enable:** `perp_hedge_enabled = True`

### How It Works

```
portfolio_delta = Σ(lots × approx_delta × 0.001 BTC) for all positions
                 CE lots → negative delta (sold calls lose when BTC rises)
                 PE lots → positive delta (sold puts lose when BTC falls)

target_perp_lots = round(-portfolio_delta × hedge_ratio / 0.001)

effective_delta = portfolio_delta + perp_delta
```

When `|effective_delta| > rebalance_band`, the perp position is adjusted.

### Safety Features

- **Flip rate limiter:** Max 6 direction flips per hour (prevents spread drag in choppy markets)
- **Cooldown:** 30s between hedge adjustments
- **Pre-adjustment projection:** When an adjustment is about to fire, the expected delta change is projected into the hedge computation (proactive, not reactive)
- **Auto-close on session stop:** Perp position is closed FIRST before any other cleanup
- **Position cap mode:** When options position cap hit, rebalance band widens to 3× to reduce perp churn

**Known limitation:** Uses hardcoded delta ≈ 0.5 for all options. Real delta varies 0.0–1.0 depending on moneyness.

---

## 15. Whipsaw Protection (Graduated)

Whipsaw = rapid alternating adjustments (CE → PE → CE or PE → CE → PE).

The current system uses a **graduated score-based approach** (not the old binary pause):

### Score System

| Score | State | Effect |
|---|---|---|
| 0–1 | NORMAL | No effect |
| 2 | CAUTION | Warning — logged but adjustments continue |
| 3 | RESTRICT | Hedge-side lots reduced by 50% |
| 4+ | COOLDOWN | Skip one adjustment interval, then score −2 |

### How Score Changes

- **+1:** When an adjustment fires in the OPPOSITE direction to the last one, within a `whipsaw_window` (default 30 minutes), AND spot moved less than `whipsaw_min_spot_move_pct`
- **−1:** For each full `adjustment_interval` without noise
- **−2:** After COOLDOWN completes

### Migration

Old sessions with the binary `_whipsaw_paused_at` flag are automatically migrated to the new score system on first heartbeat.

---

## 16. Lot Velocity Limiter

Prevents runaway lot accumulation during fast markets.

**How it works:** Counts total lots sold (both sides combined) in a rolling window. Operator-initiated adjustments are excluded from the count.

| State | Condition | Effect |
|---|---|---|
| Normal | lots_in_window < 80% of limit | No effect |
| Warning | lots_in_window ≥ 80% of limit | Warning shown |
| Blocked | lots_in_window ≥ limit | Adjustments blocked |

**Default:** 10 lots per 30 minutes.

Enable/disable: `lot_velocity_enabled` (default: `True`).

---

## 17. Advanced: Split Ledger

The Split Ledger separates position tracking into two buckets per side:

| Bucket | What It Contains | Counts Against |
|---|---|---|
| **Active lots** | Current sell positions at active strike | `max_lots_per_side` cap |
| **Frozen lots** | Positions at prior strikes (after shifts) | Only `max_total_exposure` |

### Unified Position Ledger

All positions are stored in a single `positions[]` array per side. Each position has:
- `_pos_id`: Unique identifier
- `status`: 'active', 'frozen', 'shifted', 'closed'
- `lots`, `strike`, `entry_price`, `type` (original, adjustment, strike_shift, etc.)

The `recompute_side_lots()` function rebuilds all derived fields from `positions[]` every heartbeat:
- `active_lots` = sum of lots where status is 'active'
- `frozen_total_lots` = sum of lots where status is 'frozen' or 'shifted'
- `total_lots` = `active_lots` + `frozen_total_lots`
- `adjustment_fills[]` = view of adjustment-type positions
- `frozen_positions[]` = view of frozen positions

**Key params:**
- `max_lots_per_side` — cap on active lots (primary gate)
- `max_total_exposure` — absolute ceiling on active + frozen (0 = auto: 2× max_lots)

---

## 18. Settings Hot-Reload

Most parameters can be changed WHILE the session is running and take effect on the next heartbeat. Changes via the Settings panel in the WebUI are automatically detected.

**Hot-reloadable parameters include:**
- All threshold values (min_trigger_move, shift_threshold, close_at_threshold, max_loss_amount)
- Interval settings
- Safety limits (max_lots_per_side, max_adjustments, whipsaw_limit)
- All regime control parameters
- Lot velocity limiter
- Gamma-aware multiplier
- Wind-down settings
- Margin guardian thresholds
- Perp hedge parameters (ratio, thresholds, flip limits)

**NOT hot-reloadable (require session restart):**
- `initial_lots`, `expiry`, `desired_ce_premium`, `desired_pe_premium`
- API keys, trading mode

**Cross-parameter validation:** When you change a parameter, the system validates interdependencies:
- `wind_down_close_threshold ≥ close_at_threshold`
- Margin tier ordering: green < yellow < orange < red < critical
- Whipsaw score ordering: caution < restrict < cooldown
- Trend tier ordering: tier1 < tier2 < tier3 < tier4
- Gamma limits: soft < hard < emergency

---

## 19. Common Scenarios & What to Do

### "Session Paused — Max Adjustments Reached"

The `adjustment_count` reached `max_adjustments` (default 500). The algo stops adding lots but CLOSE-AT-5 STILL RUNS. Options will naturally decay and close.

**Action:** Either wait for positions to close naturally, or raise `max_adjustments` in Settings (hot-reload). The session auto-resumes when the limit is raised.

### "Whipsaw COOLDOWN — Score ≥ 4"

BTC is ranging in a narrow band, triggering CE and PE alternately. The whipsaw score hit COOLDOWN level. The algo skips one interval and reduces the score by 2.

**Action:** None required. If whipsaw persists, consider raising `min_trigger_move` to reduce sensitivity. You can also force a heartbeat to clear the consecutive-direction block.

### "Position Cap Reached — M2 Recycling"

Active lots hit `max_lots_per_side`. M2 attempts to recycle cheap frozen lots into a new sell at a better strike.

**Action:** If M2 succeeds, lots are freed and the adjustment proceeds. If M2 fails (no viable recycle candidates), the adjustment is skipped. Consider raising `max_lots_per_side` via Settings.

### "Regime BLOCK_ALL_SELLS"

Regime controls detected unfavorable conditions (vol spike, gamma cap, trend T3+). All new sells are blocked.

**Action:** Wait for conditions to normalize. Regime controls auto-reset when IV calms / trend reverses / gamma reduces. Close-at-5 and wind-down STILL RUN (they're risk-reducing, not risk-adding).

### "ATM Shield Fired"

Spot price approached your active strike. ATM Shield closed the endangered side and re-positioned at a safer OTM strike.

**Action:** Monitor the new position. ATM Shield fires up to 3× per session by default. If the market keeps trending toward your new strike, consider manually winding down.

### "Peak P&L Decay — Trailing Stop"

If `trailing_stop_pct` is set and P&L has dropped from its peak, adjustments are blocked. The peak decays with a 15-minute half-life to prevent permanent lockout.

**Action:** The trailing stop only blocks MORE adjustments — existing positions still close normally via close-at-5. The peak will naturally decay, eventually allowing adjustments to resume.

### "One Side Closed — Session Paused"

All CE (or PE) positions closed while the other side still has open positions. The session is paused because you have unhedged exposure.

**Action:** Either close the other side manually, or re-enter the closed side at a new strike using the position inject feature.

### "Margin CRITICAL — Session Force-Stopped"

3+ consecutive CRITICAL margin beats triggered `force_stop_session`. All positions were closed first.

**Action:** Reduce position size, lower `max_lots_per_side`, or free up margin on the exchange.

### "Both Sides Fully Closed"

All positions on both CE and PE closed (decayed to close-at-5 or time expired). Session ends automatically. Perp hedge position is closed first.

**Action:** Check final P&L in the session summary. Start a new session for the next expiry.

---

## 20. Parameters Reference Table

### Core Parameters

| Parameter | Default | Hot-Reload | Description |
|---|---|---|---|
| `desired_ce_premium` | 100.0 | No | Target CE premium at entry |
| `desired_pe_premium` | 100.0 | No | Target PE premium at entry |
| `initial_lots` | 10 | No | Lots per side at entry |
| `expiry` | — | No | Contract expiry DDMMYYYY |
| `min_trigger_move` | 10.0% | Yes | % rise in premium to trigger adjustment |
| `shift_threshold` | 50.0 | Yes | Premium below which a shift is triggered (USD) |
| `shift_target_premium` | 100.0 | Yes | Target premium at new strike after shift |
| `close_at_threshold` | 5.0 | Yes | Premium at or below which positions are closed |
| `adjustment_interval` | 300s | Yes | Heartbeat interval (overridden by adaptive) |
| `max_lots_per_side` | 100 | Yes | Cap on active lots per side |
| `max_total_exposure` | 0 (auto) | Yes | Ceiling on active+frozen lots (0 = 2x max_lots) |
| `premium_buffer_pct` | 5% | Yes | Extra lots for slippage |
| `max_adjustments` | 500 | Yes | Adjustments before pause |
| `max_loss_amount` | 5000 | Yes | Hard stop P&L (USD) |
| `trailing_stop_pct` | 0 | Yes | 0 = disabled. 0.5 = protect 50% of peak |

### Safety Parameters

| Parameter | Default | Description |
|---|---|---|
| `whipsaw_caution_score` | 2 | Score for CAUTION state |
| `whipsaw_restrict_score` | 3 | Score for RESTRICT state |
| `whipsaw_cooldown_score` | 4 | Score for COOLDOWN state |
| `whipsaw_window_mins` | 30 | Lookback window for noise detection |
| `lot_velocity_enabled` | True | Enable lot velocity limiter |
| `lot_velocity_limit` | 10 | Max lots per velocity window |
| `lot_velocity_window_mins` | 30 | Velocity window in minutes |
| `stop_adjustment_mins` | 15 | Stop adjustments N mins before expiry |
| `auto_close_mins` | 5 | Auto-close all N mins before expiry |

### Regime Control Parameters

| Parameter | Default | Description |
|---|---|---|
| `regime_enabled` | False | Master switch (disabled by default) |
| `vol_regime_enabled` | True | Enable IV/RV filter |
| `vol_iv_spike_pct` | 30 | IV change % to trigger HIGH |
| `vol_rv_threshold` | 80 | Realized vol % to trigger HIGH |
| `gamma_cap_enabled` | True | Enable dollar gamma cap |
| `gamma_soft_limit` | 2500 | Dollar gamma soft limit |
| `gamma_hard_limit` | 5000 | Dollar gamma hard limit |
| `gamma_emergency_limit` | 10000 | Dollar gamma emergency limit |
| `trend_enabled` | True | Enable trend guard |
| `trend_tier1_pct` | 1.0 | % move for Tier 1 (Alert) |
| `trend_tier2_pct` | 2.0 | % move for Tier 2 (Guard) |
| `trend_tier3_pct` | 3.0 | % move for Tier 3 (Block) |
| `trend_tier4_pct` | 5.0 | % move for Tier 4 (Wind-Down) |
| `trend_tier1_lot_reduction` | 30% | Lot reduction at Tier 1 |

### Lot Lifecycle Parameters

| Parameter | Default | Description |
|---|---|---|
| `harvest_enabled` | True | Enable M1 profit harvesting |
| `harvest_profit_pct` | 40 | Minimum decay % for harvest |
| `harvest_min_age_mins` | 30 | Minimum freeze age for harvest |
| `harvest_pressure_threshold` | 0.6 | Capacity pressure to trigger harvest |
| `recycle_min_premium_ratio` | 2.5 | New/old premium ratio for M2 viability |
| `recycle_min_lot_gain` | 5 | Minimum net lot gain for M2 |
| `recycle_cooldown_sec` | 300 | Cooldown between recycle attempts |

### Margin Guardian Parameters

| Parameter | Default | Description |
|---|---|---|
| `margin_monitor_enabled` | True | Enable margin monitoring |
| `margin_green_pct` | 50 | GREEN tier threshold |
| `margin_yellow_pct` | 60 | YELLOW tier (block sells) |
| `margin_orange_pct` | 75 | ORANGE tier (wind-down) |
| `margin_red_pct` | 85 | RED tier (emergency) |
| `margin_critical_pct` | 90 | CRITICAL tier (survival) |
| `consecutive_critical_threshold` | 3 | CRITICAL beats before force-stop |

### Perp Hedge Parameters

| Parameter | Default | Description |
|---|---|---|
| `perp_hedge_enabled` | False | Enable perpetual futures hedge |
| `perp_hedge_ratio` | 1.0 | Hedge ratio (1.0 = full neutralization) |
| `perp_hedge_delta_threshold` | 0.02 | Min delta to open hedge |
| `perp_hedge_rebalance_band` | 0.005 | Min delta change to rebalance |
| `perp_hedge_max_lots` | 50 | Max perp lots |
| `perp_hedge_max_flips_per_hour` | 6 | Max direction flips per hour |
| `perp_hedge_cooldown_sec` | 30 | Cooldown between adjustments |

### ATM Shield Parameters

| Parameter | Default | Description |
|---|---|---|
| `atm_shield_enabled` | False | Enable ATM Shield |
| `atm_shield_proximity_pct` | 0.5 | % of spot for trigger proximity |
| `atm_shield_target_otm_pct` | 1.0 | Target OTM % for retreat strike |
| `atm_shield_max_per_session` | 3 | Max fires per session |

### March 2026 Parameters

| Parameter | Default | Description |
|---|---|---|
| `proactive_shift_enabled` | True | Proactively shift decaying side before close-at-5 |
| `gamma_aware_enabled` | True | Apply lot multiplier for large excess_pct |
| `gamma_aware_max_multiplier` | 1.3 | Cap on gamma-aware multiplier |
| `perp_hedge_project_adjustment` | True | Pre-project adjustment delta into perp hedge |
| `wind_down_on_atm` | False | Activate wind-down when spot hits active strike |
| `close_at_atm` | False | Emergency close all when spot hits active strike |

---

*For code-level details and architecture, see [AI_MMM_CONTEXT.md](AI_MMM_CONTEXT.md). For the code quality audit, see [MMM_CODE_QUALITY_AUDIT.md](MMM_CODE_QUALITY_AUDIT.md).*
