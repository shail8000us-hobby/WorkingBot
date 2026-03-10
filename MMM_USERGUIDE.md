# MMM User Guide — Money Mind & Method Algorithm

> **Audience:** Traders running the MMM BTC options bot via the WebUI.
> **Last Updated:** March 10, 2026
> **Exchange:** Delta Exchange India | **Instrument:** BTC 0DTE / weekly options
> **Lot Size:** 0.001 BTC per lot

---

## Table of Contents

1. [What MMM Does](#1-what-mmm-does)
2. [Quick Start — New Session](#2-quick-start--new-session)
3. [Understanding the Dashboard](#3-understanding-the-dashboard)
4. [Key Parameters Explained](#4-key-parameters-explained)
5. [Safety Systems](#5-safety-systems)
6. [Regime Controls](#6-regime-controls)
7. [Lot Lifecycle (M1 / M2 / M3)](#7-lot-lifecycle-m1--m2--m3)
8. [Strike Shift & Proactive Shift](#8-strike-shift--proactive-shift)
9. [Close-at-5 & Wind-Down](#9-close-at-5--wind-down)
10. [Margin Guardian](#10-margin-guardian)
11. [Perpetual Futures Delta Hedge](#11-perpetual-futures-delta-hedge)
12. [Whipsaw Protection](#12-whipsaw-protection)
13. [Lot Velocity Limiter](#13-lot-velocity-limiter)
14. [Advanced: Split Ledger](#14-advanced-split-ledger)
15. [Settings Hot-Reload](#15-settings-hot-reload)
16. [Common Scenarios & What to Do](#16-common-scenarios--what-to-do)
17. [Parameters Reference Table](#17-parameters-reference-table)

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
- Premium decay on unopened positions (time value erosion)
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
| **Active** | Currently open. Counted against `max_lots_per_side` cap. |
| **Frozen** | Closed by adjustment sell at a different strike. Original position bought back, replaced by new one. These lots are "frozen" until M1/M2/close-at-5 handles them. |

**Active lots** drive the position cap. Frozen lots only count against `max_total_exposure` (the absolute ceiling).

### Heartbeat Status

| Status | Meaning |
|---|---|
| 🟢 Running | Normal — heartbeat firing as expected |
| 🟡 Paused | Max adjustments hit, whipsaw detected, or max loss approaching |
| 🔴 Stopped | Session ended — manually, by safety, or both-sides-closed |
| ⚡ Partial Beat | Exchange unreachable — running safety checks with cached prices |

---

## 4. Key Parameters Explained

### Adjustment Trigger

```
trigger_snapshot = premium at the moment the LAST adjustment on this side happened
                  (or entry price if no adjustments yet)

triggered = (current_premium − trigger_snapshot) / trigger_snapshot × 100
            > min_trigger_move (%)
```

**`min_trigger_move`** (default: 10%) — how much the premium must rise above its snapshot level before the algo reacts. Higher = fewer adjustments, more tolerance. Lower = faster reaction, more lots sold.

### Shift Threshold

**`shift_threshold`** (default: 50 USD) — if premium falls below this, a strike shift is triggered. The algo closes the current position and sells at a fresh OTM strike with higher premium.

### Close-at-5

**`close_at_threshold`** (default: 5 USD) — any position with premium ≤ this is bought back (position closed, profit locked).

### Max Loss

**`max_loss_amount`** (default: 5000 USD) — if total P&L falls to −this value, ALL positions are automatically closed. Hard stop.

### Trailing Stop

**`trailing_stop_pct`** (default: 0 = disabled) — once P&L peaks, if it drops below `peak × trailing_stop_pct`, adjustments are blocked. Set to e.g. 0.5 to protect 50% of peak profit.

---

## 5. Safety Systems

MMM has 8 safety checks that run every heartbeat BEFORE any adjustment:

| Check | What It Catches | Action |
|---|---|---|
| **Position Cap** | `active_lots ≥ max_lots_per_side` | Block sells on that side |
| **Total Exposure** | `active + frozen ≥ max_total_exposure` | Block sells on that side |
| **Max Adjustments** | `adjustment_count ≥ max_adjustments` | Pause session |
| **Max Loss** | `total_pnl ≤ −max_loss_amount` | Auto-close ALL positions |
| **Whipsaw** | Rapid CE→PE→CE or PE→CE→PE alternation | Pause session for 2 intervals |
| **Asymmetry** | CE and PE lots are wildly imbalanced | Warning only |
| **Near Expiry** | Close to `stop_adjustment_mins` or `auto_close_mins` | Stop adjustments / auto-close |
| **Lot Velocity** | Too many lots sold in 30 minutes | Block sells |
| **P&L Guardrail** | P&L below configurable warning thresholds | Warning → Pause → Stop |
| **Trailing Stop** | P&L fell below `peak × trailing_stop_pct` | Block sells |

---

## 6. Regime Controls

Regime controls are **pre-adjustment risk intelligence** — they block or reduce adjustments when market conditions are unfavorable. All guarded by master switch `regime_enabled` (default: **disabled** until you opt in).

### Volatility Regime

Monitors IV change rate and realized volatility. Tiers:

| Tier | Condition | Action |
|---|---|---|
| NORMAL | IV calm | No effect |
| ELEVATED | IV rising | Warning |
| HIGH | IV spike `>vol_iv_spike_pct` | `block_sells` (or `pause`/`wind_down`) |

### Gamma Cap

Estimates portfolio dollar gamma exposure. When it exceeds limits:

| Level | Condition | Action |
|---|---|---|
| Soft limit | `dollar_gamma > gamma_soft_limit` | Warning |
| Hard limit | `dollar_gamma > gamma_hard_limit` | Block new sells |
| Emergency | `dollar_gamma > gamma_emergency_limit` | Force reduce positions |

### Trend Guard (4-tier)

Detects BTC spot directional momentum:

| Tier | Spot Move from Anchor | Effect |
|---|---|---|
| 0 | < `trend_tier1_pct` | Normal |
| 1 (Alert) | ≥ `trend_tier1_pct` | Lots reduced by `trend_tier1_lot_reduction` (default 30%) |
| 2 (Guard) | ≥ `trend_tier2_pct` | Block sells on aggressor side |
| 3 (Block) | ≥ `trend_tier3_pct` | Block ALL sells |
| 4 (Wind-Down) | ≥ `trend_tier4_pct` | Auto wind-down mode |

---

## 7. Lot Lifecycle (M1 / M2 / M3)

### M1 — Profit Harvesting

Every heartbeat, MMM scans frozen positions. If a position has:
- Decayed enough (premium fell by `harvest_profit_pct`% from entry), AND
- Been frozen long enough (`harvest_min_age_mins` minutes), AND
- Capacity pressure is high enough (`harvest_pressure_threshold`)

→ The position is bought back, locking in profit and freeing frozen lots.

### M2 — Lot Recycling

When the position cap blocks a needed adjustment, M2 runs:
1. **Phase A**: Buy back cheap frozen lots (near-worthless positions)
2. **Phase B**: Sell at a new strike with higher premium, netting MORE lots than were freed

If Phase B fails, Phase A is fully rolled back — no P&L distortion.

Trigger: `is_position_cap` returned by `calculate_lots_to_sell()`.

### M3 — Asymmetry Rebalancing

During M1 harvesting, if CE and PE lots are heavily imbalanced (one side has `rebalance_asymmetry_threshold`× more lots), M3 boosts the harvesting priority on the over-loaded side to naturally rebalance over time.

---

## 8. Strike Shift & Proactive Shift

### Normal Strike Shift

Triggered when a side's premium falls below `shift_threshold`:

1. Find a new OTM strike with premium ≥ `shift_target_premium`
2. Freeze current positions (move to frozen state)
3. Optionally buy back cheap frozen positions (shift-time recycle, if enabled)
4. Sell at new strike

### Proactive Shift Scanner (NEW — March 2026)

Every heartbeat, BEFORE close-at-5, the scanner checks all sides. If a side's premium is between `close_at_threshold` and `shift_threshold` AND it has active lots, a shift is triggered proactively — without waiting for the trigger to fire on the opposite side.

This prevents: premium decaying all the way to close-at-5 range before shifting.

Enable/disable: `proactive_shift_enabled` (default: `True`).

---

## 9. Close-at-5 & Wind-Down

### Close-at-5

Every heartbeat, all positions (active AND frozen) are scanned. Any position with `bid_price ≤ close_at_threshold` is bought back — locking in premium.

**Note:** Close-at-5 uses **bid price** (not mark). For illiquid far-OTM options, bid reflects actual buyback cost accurately.

### Wind-Down Mode

Activated by setting `wind_down_enabled = True` (or automatically when original strike goes ATM if `wind_down_on_atm = True`).

In wind-down:
- Instead of selling more lots when triggered, the algo REDUCES its position
- Uses LIFO order (most recently added frozen lots bought back first)
- Buyback fraction per trigger: `wind_down_buyback_pct` (default 25%)
- Elevated close threshold during wind-down: `wind_down_close_threshold` (default 20 USD)

Wind-down activates automatically N hours before expiry when `wind_down_hours_before_expiry` is set.

### Auto-Close (End of Day)

At `auto_close_mins` before expiry (default: 5 minutes), ALL remaining positions are closed regardless of premium. This is the final safety net — options expire worthless at 21:30 IST.

---

## 10. Margin Guardian

Real-time margin utilization monitoring from Delta Exchange.

**Enable:** `margin_monitor_enabled = True`

### Tier Thresholds (default values)

| Tier | Utilization | Action |
|---|---|---|
| 🟢 GREEN | < 50% | Normal — no restrictions |
| 🟡 YELLOW | 50–60% | Block ALL new sells |
| 🟠 ORANGE | 60–75% | Aggressive buyback of losing positions |
| 🔴 RED | 75–85% | Emergency reduce — taker orders, close positions |
| ⛔ CRITICAL | > 85% | Survival — close ALL, stop session |

**Consecutive CRITICAL escalation:** After 3 consecutive heartbeats at CRITICAL (configurable via `consecutive_critical_threshold`), the session is force-stopped even before RED/CRITICAL tier handling. This prevents margin calls during exchange delays.

Margin utilization formula (from exchange):
```
utilization% = (position_margin + order_margin) / net_equity × 100
```

---

## 11. Perpetual Futures Delta Hedge

Optional delta neutralization via BTC perpetual futures.

**Enable:** `perp_hedge_enabled = True`

The hedge computes:
```
portfolio_delta = Σ(lots × approx_delta × 0.001 BTC) for all positions
                 CE lots → negative delta (sold calls)
                 PE lots → positive delta (sold puts)
```

When `|portfolio_delta| > perp_hedge_delta_threshold`, a perp position is taken to neutralize delta to near-zero.

**Modes:**
- `full` — always hedge delta
- `atm_only` — only hedge when original strike is within `perp_hedge_atm_threshold_pct`% of spot (high-gamma zone)

**Pre-Adjustment Projection:** When an adjustment is about to fire, the expected delta change from the new lots is projected into the hedge computation, so the perp adjusts proactively rather than reactively.

---

## 12. Whipsaw Protection

Whipsaw = rapid alternating adjustments (CE → PE → CE or PE → CE → PE).

**How it works:**
1. Every time an adjustment fires and the direction is OPPOSITE to the last one, a pre-filter counter increments.
2. The main whipsaw check looks at the last `whipsaw_limit` (default 3) adjustments.
3. If the pre-filter counter reaches `whipsaw_limit - 1`, the threshold effectively drops by 1 (fires one beat earlier).
4. When whipsaw is detected: pause for `adjustment_interval × 2` seconds, then auto-resume.

**Tuning:**
- Increase `whipsaw_limit` to tolerate more alternation before pausing.
- Decrease `adjustment_interval` for faster whipsaw recovery.

---

## 13. Lot Velocity Limiter

Prevents runaway lot accumulation during fast markets.

**How it works:** Counts total lots sold (both sides combined) in a rolling window. If the rate exceeds `lot_velocity_limit` in `lot_velocity_window_mins` minutes, adjustments are blocked until the window rolls forward.

| State | Condition | Effect |
|---|---|---|
| Normal | lots_in_window < 80% of limit | No effect |
| Warning | lots_in_window ≥ 80% of limit | Warning shown |
| Blocked | lots_in_window ≥ limit | Adjustments blocked |

**Default:** 10 lots per 30 minutes.

Enable/disable: `lot_velocity_enabled` (default: `True`).

---

## 14. Advanced: Split Ledger

The Split Ledger separates position tracking into two buckets per side:

| Bucket | What It Contains | Counts Against |
|---|---|---|
| **Active lots** | Current sell positions | `max_lots_per_side` cap |
| **Frozen lots** | Bought-back positions from prior strikes | Only `max_total_exposure` |

**Before Split Ledger:** Every lot (including long-ago frozen positions) counted against the cap. Getting close to the cap triggered M2 recycling aggressively.

**After Split Ledger:** Only the CURRENT active positions count against the cap. Frozen positions accumulate freely (up to `max_total_exposure`) and are handled by M1/M2/close-at-5 at their own pace.

**Key params:**
- `max_lots_per_side` — cap on active lots (primary gate)
- `max_total_exposure` — absolute ceiling on active + frozen (0 = auto: 2× max_lots)

---

## 15. Settings Hot-Reload

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

**NOT hot-reloadable (require session restart):**
- `initial_lots`, `expiry`, `desired_ce_premium`, `desired_pe_premium`

---

## 16. Common Scenarios & What to Do

### "Session Paused — Max Adjustments Reached"

The `adjustment_count` reached `max_adjustments` (default 500). The algo stops adding lots but CLOSE-AT-5 STILL RUNS. Options will naturally decay and close.

**Action:** Either wait for positions to close naturally, or raise `max_adjustments` in Settings (hot-reload).

### "Whipsaw Detected — Pausing"

BTC is ranging in a narrow band, triggering CE and PE alternately. The algo pauses for 2 × `adjustment_interval` then auto-resumes.

**Action:** None required. If whipsaw repeats, consider raising `min_trigger_move` or `whipsaw_limit`.

### "Position Cap Reached — M2 Recycling"

Active lots hit `max_lots_per_side`. M2 attempts to recycle cheap frozen lots into a new sell at a better strike.

**Action:** If M2 succeeds, lots are freed and the adjustment proceeds. If M2 fails, the adjustment is skipped that beat. Consider raising `max_lots_per_side` via Settings.

### "Peak P&L Decay — Trailing Stop Approached"

If `trailing_stop_pct` is set and P&L has dropped from its peak, adjustments will be blocked when P&L drops below `peak × trailing_stop_pct`.

**Action:** The trailing stop only blocks MORE adjustments — existing positions still close normally via close-at-5.

### "Margin CRITICAL — Session Force-Stopped"

3+ consecutive CRITICAL margin beats triggered `force_stop_session`. All positions were closed first.

**Action:** Reduce position size, lower `max_lots_per_side`, or free up margin on the exchange.

### "Both Sides Fully Closed"

All positions on both CE and PE closed (decayed to close-at-5 or time expired). Session ends automatically.

**Action:** Check final P&L in the session summary. Start a new session for the next expiry.

### "Proactive Shift Triggered"

A side's premium decayed below `shift_threshold` while the algo was between adjustment cycles. The shift ran proactively before close-at-5 processing.

**Action:** Normal operation. The side shifted to a better OTM strike. No action needed.

---

## 17. Parameters Reference Table

### Core Parameters

| Parameter | Default | Hot-Reload | Description |
|---|---|---|---|
| `desired_ce_premium` | 100.0 | ❌ | Target CE premium at entry |
| `desired_pe_premium` | 100.0 | ❌ | Target PE premium at entry |
| `initial_lots` | 10 | ❌ | Lots per side at entry |
| `expiry` | — | ❌ | Contract expiry DDMMYYYY |
| `min_trigger_move` | 10.0% | ✅ | % rise in premium to trigger adjustment |
| `shift_threshold` | 50.0 | ✅ | Premium below which a shift is triggered (USD) |
| `shift_target_premium` | 100.0 | ✅ | Target premium at new strike after shift |
| `close_at_threshold` | 5.0 | ✅ | Premium at or below which positions are closed |
| `adjustment_interval` | 300s | ✅ | Heartbeat interval (overridden by adaptive) |
| `max_lots_per_side` | 100 | ✅ | Cap on active lots per side |
| `max_total_exposure` | 0 (auto) | ✅ | Ceiling on active+frozen lots (0 = 2× max_lots) |
| `premium_buffer_pct` | 5% | ✅ | Extra lots for slippage |
| `max_adjustments` | 500 | ✅ | Adjustments before pause |
| `max_loss_amount` | 5000 | ✅ | Hard stop P&L (USD) |
| `trailing_stop_pct` | 0 | ✅ | 0 = disabled. 0.5 = protect 50% of peak |

### Safety Parameters

| Parameter | Default | Description |
|---|---|---|
| `whipsaw_limit` | 3 | Alternating adjustments before pause |
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
| `gamma_cap_enabled` | True | Enable dollar gamma cap |
| `trend_enabled` | True | Enable trend guard |
| `trend_tier1_lot_reduction` | 30% | Lot reduction at Tier 1 |

### New March 2026 Parameters

| Parameter | Default | Description |
|---|---|---|
| `proactive_shift_enabled` | True | Proactively shift decaying side before close-at-5 |
| `gamma_aware_enabled` | True | Apply lot multiplier for large excess_pct |
| `gamma_aware_max_multiplier` | 1.3 | Cap on gamma-aware multiplier |
| `consecutive_critical_threshold` | 3 | Margin CRITICAL beats before force-stop |
| `perp_hedge_project_adjustment` | True | Pre-project adjustment delta into perp hedge |

---

*For technical details, algorithm internals, and code structure, see [AI_MMM_CONTEXT.md](AI_MMM_CONTEXT.md). For the original design rationale, see [MONEY_POWER_ALGORITHM_PLAN.md](MONEY_POWER_ALGORITHM_PLAN.md) (historical reference only).*
