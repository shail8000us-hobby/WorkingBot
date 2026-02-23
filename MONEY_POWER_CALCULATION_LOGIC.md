# MONEY POWER — Pure Calculation Logic (Definitive)

> Sell CE + PE on BTC options. Whenever one side's loss grows beyond what's already covered, sell more of the opposite side to collect premium that covers the new loss. If the opposing premium is too low, shift to a closer strike. Close any position at ≤5 premium. Optionally hedge directional risk with BTC perpetual futures. Repeat until expiry or user stops.
>
> **Last Updated:** February 22, 2026 — Added: Perpetual Futures Delta Hedge (§23), Regime Controls (§24), Margin Guardian (§25), Decimal arithmetic, Unified Position Ledger, production hardening notes.

---

## SECTION 1: TERMS

| Term | Meaning |
|------|---------|
| **CE** | Call option at strike X |
| **PE** | Put option at strike Y |
| **Premium** | The price of the option. When you SELL, you collect this. When it goes UP after selling, you lose money. |
| **Lots** | Number of contracts. |
| **Trigger** | A reference premium level per side. If current premium exceeds this, an adjustment is needed. |
| **Adjustment** | Selling additional lots of the opposite side to cover a new loss. |
| **Aggressor** | The side whose premium is rising (causing loss). |
| **Hedge side** | The side we sell more of to cover the aggressor's loss. |
| **Original positions** | The initial CE and PE lots sold at entry. These naturally offset each other. |
| **Adjustment positions** | Extra lots sold AFTER entry to cover losses on the other side. These are naked extra risk. |
| **Active strike** | The strike currently being monitored and used for new adjustments on a given side. Can change via strike shift. |
| **Shifted positions** | Positions at a previous strike after a strike shift. Still open, **fully tracked, fully included in ALL loss calculations**. They are live risk until closed (via close-at-5 or max-loss stop). The internal code still uses the variable name `frozen_positions` for backward compatibility, but semantically they are NOT frozen — they are active risk. |
| **Strike shift** | Moving to a closer-to-ATM strike when the current strike's premium is too low for effective hedging. Old positions stay open and fully tracked. |
| **shift_target_premium** | Target premium when selecting a new strike during a shift (default 100). Picks the strike whose premium is closest to this value. |
| **Reversal** | When the market changes direction — the side that was declining now starts rising. |
| **Trigger snapshot** | A record of premiums at all active strikes at the moment triggers were last updated. |

---

## SECTION 2: STATE

The algo maintains this information at all times:

### Per-Side State (CE and PE each have their own copy)

```
original_lots          — lots sold at entry
original_premium       — premium per lot at entry
original_strike        — strike price at entry

active_strike          — current strike used for monitoring (starts as original_strike, changes on shift)

adjustment_fills       — list of all adjustment sells at the ACTIVE strike: [{lots, premium, strike, timestamp}]
adjustment_total_lots  — sum of lots in adjustment_fills at active strike
adjustment_avg         — weighted average premium of adjustment_fills at active strike

frozen_positions       — list of positions at OLD strikes after shift: [{strike, lots, entry_premium}]
                         (still called "frozen" in code for backward compat, but these are NOT excluded from calculations — they are live risk)
frozen_total_lots      — sum of lots in frozen_positions (always included in loss calculations)

active_lots            — original_lots + adjustment_total_lots (lots at active strike only)
total_lots             — active_lots + frozen_total_lots (all lots across all strikes)

trigger_snapshot       — {strike: premium_at_last_trigger_update} for each strike with positions
```

### Global State

```
last_aggressor         — "CE" or "PE" or "NONE"
adjustment_count       — total number of adjustments made
adjustment_history     — ordered list: [{side, lots_sold, premium, strike, timestamp}]
realized_pnl           — cumulative P&L from close-at-5 events (locked profit)
total_premium_collected — sum of ALL premiums collected from ALL sells
strategy_status        — "RUNNING" | "PAUSED" | "STOPPED" | "BOTH_SIDES_UP"
peak_pnl               — high-water mark for trailing stop (decays: 0.9×old + 0.1×current when below peak)
_pnl_calculation_incomplete — bool, set when >50% of premium fetches fail
_watchdog_restarts     — count of monitor auto-restarts
```

### Perp Hedge State (if perp_hedge_enabled)

```
perp_hedge.enabled           — bool, whether delta hedge is active
perp_hedge.direction         — "LONG" | "SHORT" | "FLAT"
perp_hedge.lots              — current perp position lots
perp_hedge.entry_price       — average entry price
perp_hedge.effective_delta   — most recent portfolio delta calculation
perp_hedge.unrealized_pnl    — mark-to-market P&L on perp position
perp_hedge.realized_pnl      — closed P&L from perp trades
perp_hedge.last_rebalance    — ISO timestamp of last rebalance
perp_hedge.trade_count       — total perp trades this session
perp_hedge.cooldown_until    — ISO timestamp when cooldown expires
```

### Unified Position Ledger (Implementation Detail)

All positions (original, adjustment, frozen/shifted) are stored in a single `positions[]` list per side. Each position has a unique `_pos_id`. All computed views (`active_lots`, `total_lots`, `frozen_total_lots`, `adjustment_total_lots`, `adjustment_avg`) are derived by calling `recompute_side_lots()`. ID-based removal for O(1) operations. Auto-migration adds `_pos_id` and `position_type` to legacy data.

### Decimal Arithmetic (Implementation Detail)

All P&L accumulation uses Python `Decimal` via `_D(x)` helper which converts through `str(x)` to avoid IEEE 754 float representation errors. This eliminates $0.50–$1.00 drift over a full session lifetime. Applies to: `realized_pnl`, `unrealized_pnl`, `total_premium_collected`, `total_fees`, and all intermediate loss calculations.

---

## SECTION 3: INITIALIZATION

### Mode A — Fresh Entry (auto-find strikes)

**User inputs on WebUI:**
1. Desired CE premium (e.g., 100)
2. Desired PE premium (e.g., 100)
3. Number of lots per side (e.g., 10)
4. Expiry (0DTE or a specific date)

**Algo does:**

```
1. Fetch BTC spot price from the exchange
2. Fetch the full options chain for the selected expiry
3. For CE: scan all CALL strikes ABOVE spot price
   → For each strike, get the mark price (mid of bid/ask)
   → Find the strike whose premium is CLOSEST to the user's desired CE premium
   → If multiple strikes are equally close, pick the one further OTM (safer)

4. For PE: scan all PUT strikes BELOW spot price
   → Same process — find strike closest to desired PE premium

5. Display to user on WebUI:
   "Found CE strike: 100000 (premium: 98.5) and PE strike: 96000 (premium: 101.2)"
   User confirms → OR → algo auto-proceeds after 5-second countdown

6. Execute: Sell N lots of CE at found strike, Sell N lots of PE at found strike
7. Record fills and set initial state (see below)
```

### Mode B — Import Existing Positions

**User inputs on WebUI:**
1. CE strike, CE entry premium, CE lots
2. PE strike, PE entry premium, PE lots
3. Expiry

The algo skips order placement and directly initializes state from these values.

### Initial State After Entry (both modes)

```
CE side:
  original_lots = N
  original_premium = CE fill price
  original_strike = CE strike
  active_strike = CE strike
  adjustment_fills = []
  adjustment_total_lots = 0
  adjustment_avg = 0
  frozen_positions = []
  frozen_total_lots = 0
  active_lots = N
  total_lots = N
  trigger_snapshot = {CE_strike: CE_fill_price}

PE side:
  (mirror of above with PE values)

Global:
  last_aggressor = "NONE"
  adjustment_count = 0
  realized_pnl = 0
  total_premium_collected = CE_fill × N + PE_fill × N
  strategy_status = "RUNNING"
```

**Example:**
```
BTC at 98000. User wants ~100 premium CE and PE, 10 lots, 0DTE.
Algo finds: CE at strike 100000 (premium 102), PE at strike 96000 (premium 98)
Sells 10 CE @ 102, 10 PE @ 98
ce_trigger_snapshot = {100000: 102}
pe_trigger_snapshot = {96000: 98}
Total premium = 1020 + 980 = 2000
```

---

## SECTION 4: EVERY CHECK INTERVAL (The Heartbeat)

Every `interval` seconds the algo does a heartbeat. The interval is **adaptive** (see §4.1 below) — it ranges from 60s to 1200s depending on how close premiums are to their triggers.

```
1. Fetch premium at active_ce_strike → CE_now
2. Fetch premium at active_pe_strike → PE_now
   — All fetches wrapped in Circuit Breaker (§13.8)
   — If >50% of fetches fail → set _pnl_calculation_incomplete, PAUSE session
3. Run CLOSE-AT-5 check on ALL positions (Section 11)
   — if wind-down mode active, use elevated threshold (Section 11.1)
4. Run SAFETY CHECKS (Section 13)
5. Run REGIME CHECKS (Section 24) — abort adjustment if regime blocks
6. If strategy_status ≠ "RUNNING" → skip adjustment logic
7. Run MARGIN GUARDIAN check (Section 25) — block sells if YELLOW+

8. Determine if adjustment is needed:
   ce_excess = CE_now - ce_trigger_snapshot[active_ce_strike]
   pe_excess = PE_now - pe_trigger_snapshot[active_pe_strike]

   Apply minimum trigger move filter (PERCENTAGE-BASED):
   ce_trigger = ce_trigger_snapshot[active_ce_strike]
   ce_threshold = ce_trigger × (min_trigger_move_pct / 100)
   ce_triggered = ce_excess > ce_threshold

   pe_trigger = pe_trigger_snapshot[active_pe_strike]
   pe_threshold = pe_trigger × (min_trigger_move_pct / 100)
   pe_triggered = pe_excess > pe_threshold

9. FOUR OUTCOMES:

   A) NOT ce_triggered AND NOT pe_triggered
      → DO NOTHING. Both sides within safe zone.

   B) ce_triggered AND NOT pe_triggered
      → CE is aggressor. Go to SECTION 5 (sell PE to cover).

   C) NOT ce_triggered AND pe_triggered
      → PE is aggressor. Go to SECTION 5 (sell CE to cover).

   D) ce_triggered AND pe_triggered
      → BOTH sides above trigger. Go to SECTION 8 (user decides).

10. Run PERP HEDGE check_and_rebalance() if enabled (Section 23)
    — Runs AFTER trigger evaluation, regardless of regime state
    — Computes portfolio delta, adjusts perp position if threshold breached
```

### 4.1 Adaptive Heartbeat Interval (Added Feb 17, 2026)

Instead of a fixed interval, the algo dynamically adjusts the check frequency based on how close premiums are to their triggers. This saves API calls when nothing is happening, and checks more frequently when action is imminent.

**Tiers:**

| Proximity to Trigger | Interval | Rationale |
|---------------------|----------|----------|
| ≥80% of trigger exceeded | 60s | Action imminent — check every minute |
| ≥50% of trigger exceeded | 120s | Getting close — monitor closely |
| ≥30% of trigger exceeded | 180s | Moderate movement — reasonable pace |
| <30% of trigger exceeded | User-set interval (default 300s) | Normal — use configured interval |
| Both premiums declining | 600–1200s (scales with distance) | Premiums moving favorably — relax |

**Formula:** The tier is determined by the maximum of `ce_excess / ce_threshold` and `pe_excess / pe_threshold`. If both premiums are below their entry triggers (i.e., decaying), the interval extends up to `adaptive_max_interval` (default 1200s = 20 minutes).

**Parameters:**
- `adaptive_interval_enabled` (default true) — master switch
- `adaptive_max_interval` (default 1200) — maximum seconds when premiums are far from triggers

### 4.2 Wind-Down Mode (Added Feb 17, 2026)

In the final hours before expiry, a coordinated wind-down system activates to gracefully close positions and avoid risky adjustments near expiry:

```
IF minutes_to_expiry ≤ wind_down_minutes (default 120 = 2 hours):
    → Wind-down mode ACTIVE
    → Three possible actions per heartbeat:
       1. BUYBACK: Close positions at elevated threshold (see §11.1)
       2. SKIP: Do nothing if positions are decaying naturally
       3. Floor action: close_all / stop_adjustments / alert (configurable)

    Wind-down checks run BEFORE normal adjustment logic.
    If wind-down buybacks close all positions → strategy COMPLETE.
```

**Parameters:**
- `wind_down_enabled` (default true) — master switch
- `wind_down_minutes` (default 120) — when wind-down activates
- `wind_down_threshold_pct` (default 25.0) — close positions at premium ≤ 25% of entry (elevated from 5)
- `wind_down_floor_action` (default 'stop_adjustments') — what to do if positions can't be closed: 'close_all', 'stop_adjustments', or 'alert'

---

## SECTION 5: ADJUSTMENT CALCULATION (Core Math)

Described for **CE as aggressor** — need to sell PE. PE-as-aggressor is the exact mirror (swap CE↔PE everywhere).

### Step 5.1 — Is this a reversal?

```
reversal = (last_aggressor == "PE" and CE is now the aggressor)

Note: if last_aggressor == "NONE" → NOT a reversal (first-ever adjustment)
Note: if last_aggressor == "CE" and CE is again the aggressor → NOT a reversal (continuation)
```

### Step 5.2 — Calculate loss to cover

**CASE A — Normal (continuation or first-ever):**

Compute total loss across ALL open positions on the aggressor side:

```
total_loss = 0

# 1. Active positions at the active strike
active_loss = (CE_now - ce_trigger_snapshot[active_ce_strike]) × ce_active_lots × LOT_SIZE_BTC
total_loss += max(active_loss, 0)

# 2. ALL shifted positions at old strikes
for each shifted_position on CE side:
    current_premium = fetch_live_premium(position.strike, "CE")
    position_loss = (current_premium - position.entry_premium) × position.lots × LOT_SIZE_BTC
    if position_loss > 0:  # only count if losing (premium rose past entry)
        total_loss += position_loss

loss_to_cover = total_loss
```

**CRITICAL:** Every open position contributes to `loss_to_cover`. The algo hedges the TOTAL exposure across ALL strikes, not just the active strike. No position is ever excluded from loss calculations.

**CASE B — First reversal:**

On a reversal, the adjustment positions on the NOW-aggressor side are the naked risk. The original CE and PE naturally offset each other. We only need to hedge the loss on the adjustment positions.

**Calculate actual P&L of all CE adjustment positions:**

```
adjustment_pnl = 0
for each fill in ce_adjustment_fills:
    current_premium = fetch_premium(fill.strike, "CE")
    adjustment_pnl += (fill.entry_premium - current_premium) × fill.lots

for each frozen in ce_frozen_positions:
    current_premium = fetch_premium(frozen.strike, "CE")
    adjustment_pnl += (frozen.entry_premium - current_premium) × frozen.lots
```

If `adjustment_pnl ≥ 0` → adjustments are still in net profit → **DO NOTHING**

If `adjustment_pnl < 0` → adjustments are underwater.
```
loss_to_cover = abs(adjustment_pnl)
```

**Why this formula?** When CE has adjustment positions (sold during a prior down-phase to cover PE losses), those positions have no natural offset. If CE now rises, they lose money. The P&L calculation tells us exactly when and by how much they're underwater.

**For the single-strike case (no prior shift), this reduces to:**
```
loss = (CE_now - ce_adjustment_avg) × ce_adjustment_total_lots
```
Which is the simpler formula. The generalized version handles multi-strike after shifts.

**After the first reversal adjustment:** set `last_aggressor` to new direction. All subsequent adjustments (until next reversal) use CASE A.

### Step 5.3 — Determine which strike to sell at

Before selling PE lots, check if the opposing side's premium is high enough:

```
pe_premium_at_active = fetch_premium(active_pe_strike, "PE")

IF pe_premium_at_active ≥ shift_threshold (default 50):
    → Sell at active_pe_strike. Price = pe_premium_at_active.
    
IF pe_premium_at_active < shift_threshold:
    → STRIKE SHIFT needed. Go to Section 10 to find a new PE strike.
    → After shift, come back with the new strike and its premium.
```

### Step 5.4 — Calculate lots to sell

$$\text{lots\_to\_sell} = \left\lceil \frac{\text{loss\_to\_cover}}{\text{hedge\_premium}} \right\rceil$$

Where `hedge_premium` is the premium at whichever strike we're selling (active or shifted).

**Apply constraints:**
```
lots_to_sell = max(lots_to_sell, 1)                         ← at least 1 lot
lots_to_sell = min(lots_to_sell, max_adjustment_lots)        ← per-adjustment cap

IF (opposing_total_lots + lots_to_sell) > max_lots_per_side:
    lots_to_sell = max_lots_per_side - opposing_total_lots
    IF lots_to_sell ≤ 0: ALERT user, skip adjustment
```

### Step 5.5 — Execute and verify

```
Sell lots_to_sell of opposing side at the selected strike.
premium_collected = lots_to_sell × fill_price

Verify: premium_collected ≥ loss_to_cover
  If yes: adjustment successful. Buffer = premium_collected - loss_to_cover
  If no: flag for user (bad fill / slippage)
```

### Step 5.6 — Update state

Go to Section 6.

---

## SECTION 6: STATE UPDATE (After Every Adjustment)

### 6.1 — Record the fill

```
IF sold at the current active strike:
    opposing_side.adjustment_fills.append({lots, premium, strike, timestamp})
    Recompute: adjustment_total_lots, adjustment_avg, active_lots, total_lots

IF sold at a NEW strike (strike shift):
    Move current active strike positions to frozen:
        frozen_positions.append({strike: old_active_strike, lots: active_lots, entry_premium: varies})
    Set active_strike = new_strike
    Reset adjustment_fills for this new strike = [{lots, premium, strike, timestamp}]
    Recompute all lots
```

### 6.2 — Update trigger snapshots

**CRITICAL RULE: Both sides' snapshots update, regardless of which side was the aggressor.**

```
ce_trigger_snapshot[active_ce_strike] = CE_now
pe_trigger_snapshot[active_pe_strike] = PE_now

Also snapshot any other strikes with active positions:
for each strike with open positions:
    trigger_snapshot[strike] = fetch_premium(strike)
```

**Why both update?**
- Aggressor side: trigger ratchets up → next adjustment only fires on NEW loss beyond this point
- Hedge side: trigger set to current price → if this side reverses and rises above this, it means the premium we just collected is being eroded

### 6.3 — Update tracking

```
last_aggressor = the aggressor side
adjustment_count += 1
total_premium_collected += premium_collected
adjustment_history.append({side, lots_sold, premium, strike, timestamp})
```

### 6.4 — Push to WebUI

Send real-time update via WebSocket:
- Updated positions table
- New trigger levels
- Premium collected this adjustment
- Total P&L
- Alert if any safety threshold approaching

---

## SECTION 7: THE TRIGGER SYSTEM

### What Triggers Are

The trigger creates a **safe zone** — a band of premiums within which no adjustment is needed.

```
After entry (CE@102, PE@98):
  Safe zone: CE ≤ 102 AND PE ≤ 98

After 1st adj (CE went to 122, sold PE at 78):
  Safe zone: CE ≤ 122 AND PE ≤ 78

After 2nd adj (CE went to 132, sold PE at 68):
  Safe zone: CE ≤ 132 AND PE ≤ 68
```

The safe zone expands in the direction of the trend. On reversal, it resets around the reversal point.

### Trigger Meaning

`ce_trigger_snapshot[strike] = X` means:
> "All CE losses at this strike up to premium X have been fully covered by premium collected from PE adjustment sells. Only losses ABOVE X are new and unhedged."

### Minimum Trigger Move (Percentage-Based)

To avoid adjusting on noise, require the premium to exceed the trigger by a percentage of the trigger level:

$$\text{threshold} = \text{trigger\_snapshot} \times \frac{\text{min\_trigger\_move\_pct}}{100}$$

$$\text{triggered} = (\text{premium\_now} - \text{trigger\_snapshot}) > \text{threshold}$$

Default `min_trigger_move_pct = 3` (3%). This is percentage-based rather than absolute, so the trigger sensitivity scales naturally with premium levels:
- At trigger 100 → threshold = 3 (need 103+ to trigger)
- At trigger 300 → threshold = 9 (need 309+ to trigger)
- At trigger 50 → threshold = 1.5 (need 51.5+ to trigger)

This prevents the problem where an absolute threshold of 3 is too sensitive at high premiums (300) and too insensitive at low premiums (20).

> **History:** Originally implemented as absolute `min_trigger_move = 3`. Converted to percentage-based on Feb 17, 2026 to scale properly across all premium levels.

---

## SECTION 8: BOTH SIDES ABOVE TRIGGER (User Decision)

This is a rare scenario. It can happen when:
- Implied volatility spikes (both CE and PE premiums increase)
- Underlying whipsaws within one interval, crossing both triggers

**THE ALGO DOES NOT AUTO-ADJUST IN THIS CASE.**

Instead:

```
1. Set strategy_status = "BOTH_SIDES_UP"
2. Show alert on WebUI:
   "⚠️ Both CE and PE premiums exceeded triggers.
    CE: {CE_now} (trigger: {ce_trigger}), excess: {ce_excess}
    PE: {PE_now} (trigger: {pe_trigger}), excess: {pe_excess}
    
    This can be an opportunity (IV spike = premiums will decay)
    or a risk (underlying moving sharply).
    
    Options:
    [A] ADD more lots to one or both sides (increase exposure)
    [B] REDUCE lots on one or both sides (decrease exposure)
    [C] RESUME with updated triggers (accept current levels as new baseline)
    [D] STOP the strategy"

3. Wait for user input.

4. Based on user action:
   If ADD: record new fills, update total_lots and triggers
   If REDUCE: close specified lots, update total_lots and triggers
   If RESUME: update both triggers to current premiums, set status = "RUNNING"
   If STOP: close all positions, end strategy
```

**Why user decides?** Both sides losing simultaneously means the position is structurally stressed. Selling MORE of either side to cover would double down on risk. The user's judgment about whether this is temporary (IV spike that will revert) or structural (market regime change) is more valuable than any automatic rule.

---

## SECTION 9: REVERSAL LOGIC

### What Is a Reversal?

The market was moving in one direction (e.g., CE was aggressor for multiple intervals), and now the OTHER side becomes the aggressor.

Detection:
```
reversal = (last_aggressor == "CE" AND pe_triggered)
        OR (last_aggressor == "PE" AND ce_triggered)
```

### The First-Reversal Problem

During an uptrend, the algo accumulated PE adjustment lots. These adjustment lots have NO matching CE counterpart — they are naked risk. The original CE and PE naturally offset each other (when PE rises, CE falls by a similar amount).

So the first reversal adjustment ONLY hedges the naked adjustment positions.

### First-Reversal Formula

Calculate the actual P&L of ALL adjustment positions on the now-aggressor side:

```
adjustment_pnl = 0
for each adjustment fill AND each frozen position on aggressor side:
    current_premium_at_that_strike = fetch_premium(fill.strike)
    adjustment_pnl += (fill.entry_premium - current_premium) × fill.lots
```

**If `adjustment_pnl ≥ 0`:** Adjustments still net positive. DO NOTHING. Wait for next interval.

**If `adjustment_pnl < 0`:** Adjustments are underwater.
```
loss_to_cover = abs(adjustment_pnl)
→ Proceed to sell opposite side lots (Section 5.3 onwards)
```

### After First Reversal → Standard Mode

Once the first reversal adjustment is done:
- Triggers are updated to current prices
- `last_aggressor` is set to the new direction
- All subsequent adjustments use the standard formula (Case A from Section 5.2):

```
total_loss = active_loss + shifted_loss
```

Where `active_loss = (premium_now - trigger_snapshot) × active_lots` and `shifted_loss` sums all shifted positions at their live premiums.

**Why include ALL positions?** After both sides have adjustment positions, the clean original/adjustment separation breaks down. Including all open positions ensures complete coverage and prevents invisible loss accumulation at old strikes.

### Cooldown After Reversal (Strength Feature)

When a reversal is detected, the algo can optionally **wait one extra interval** before adjusting:

```
IF reversal detected AND cooldown_enabled:
    → Log "Reversal detected, cooling down for 1 interval"
    → On NEXT interval, if the reversal still holds, THEN adjust
    → If it reversed back, it was noise — no adjustment needed
```

This filters out false reversals from short-lived spikes.

---

## SECTION 10: STRIKE SHIFTING

### When It Happens

The algo needs to sell lots on side X, but the premium at X's active strike is below `shift_threshold` (default: 50, configurable via WebUI during runtime).

A low opposing premium means:
- Selling lots yields very little premium per lot
- Covering the loss requires a huge number of lots
- Those lots create disproportionate risk for negligible hedge value

### Strike Discovery

```
1. Fetch the full options chain for the current expiry
2. For CE shift: scan CALL strikes ABOVE current spot price
3. For PE shift: scan PUT strikes BELOW current spot price
4. Filter: only strikes with premium ≥ shift_threshold
5. From those, select the strike whose premium is closest to
   shift_target_premium (default: 100, configurable via WebUI)
6. Prefer strikes with reasonable bid-ask spread (avoid illiquid strikes)
```

### What Changes After a Shift

**Before shift:**
```
PE active_strike = 96000 (premium: 35)
PE positions at 96000: 10 original + 5 adjustment
```

**After shift to PE strike 97500 (premium: 130):**
```
PE frozen_positions += [{strike: 96000, lots: 15, entry_premiums: [original@98, adj@70, adj@55...]}]
PE active_strike = 97500
PE adjustment_fills at 97500 = [{lots: newly_sold, premium: 130}]
PE active_lots = newly_sold lots only
PE total_lots = active_lots + frozen_total_lots
PE trigger_snapshot[97500] = 130
```

### Key Rules for Strike Shifting

1. **Old positions are NOT closed.** They stay open and are fully tracked. They contribute to total_lots for P&L monitoring and are subject to close-at-5.

2. **ALL positions (active + shifted) are used in the standard adjustment formula.** The standard loss calculation (Section 5.2 Case A) computes `active_loss + shifted_loss` where each shifted position's loss is evaluated at its current live premium. No position is ever excluded.

3. **ALL positions are included in the first-reversal P&L calculation.** When computing "are the adjustment positions underwater?", we check ALL adjustment fills including shifted ones, each at their own current premium. This is accurate because we fetch each strike's premium individually.

4. **Multiple shifts can happen.** If BTC trends strongly in one direction, you might shift 2-3 times. Each shift moves the previous active strike's positions to `shifted_positions` and starts fresh at a new strike. ALL shifted positions at ALL old strikes remain fully tracked and included in every calculation.

5. **The `shift_threshold` only controls WHERE to open NEW positions.** It answers: "Is this strike's premium high enough to sell at?" It does NOT affect whether existing positions are tracked or included in loss calculations.

6. **The `shift_target_premium` controls WHAT premium to target** when selecting a new strike (default 100). The algo picks the strike whose premium is closest to this value.

7. **The user can change `shift_threshold` and `shift_target_premium` via WebUI at any time** (hot reload).

### Example of Strike Shift

```
BTC at 100,000. Entry: CE@102,000 (prem 100), PE@98,000 (prem 100), 10 lots each.

T+5: BTC rises to 101,500
  CE@102,000 prem = 150. PE@98,000 prem = 55.
  CE triggered. Loss = (150-100) × 10 = 500
  PE at 98,000 prem = 55 ≥ shift_threshold(50) → sell at current strike
  Sell ceil(500/55) = 10 PE @ 98,000 at prem 55. Premium = 550.

T+10: BTC rises to 103,000
  CE@102,000 prem = 210. PE@98,000 prem = 30.
  CE triggered. Loss = (210-150) × 10 = 600
  PE at 98,000 prem = 30 < shift_threshold(50) → STRIKE SHIFT
  
  Scan chain: PE@100,000 prem = 120. 
  Shift active PE strike to 100,000.
  Freeze PE positions at 98,000 (10 orig + 10 adj = 20 lots frozen).
  Sell ceil(600/120) = 5 PE @ 100,000 at prem 120. Premium = 600.
  
  New state:
    PE active_strike = 100,000
    PE active_lots = 5
    PE frozen: 20 lots at 98,000
    PE total_lots = 25
    pe_trigger_snapshot[100,000] = 120
```

---

## SECTION 11: CLOSE-AT-5 RULE

### Rule

Every check interval, scan ALL positions (original, adjustment, frozen) across all strikes:

```
for each position:
    current_premium = fetch_premium(position.strike, position.type)
    IF current_premium ≤ 5:
        → BUY BACK those lots at current premium (or market)
        → Record realized profit: (entry_premium - close_premium) × lots
        → Remove from tracking
        → Update total_lots, active_lots or frozen_lots
        → Add to realized_pnl
```

### Why Close at ≤5?

- A position at premium 5 has already given you 95% of its maximum profit (if sold at ~100)
- The risk of it suddenly reversing (going from 5 to 200) is small but devastating
- Locking in profit at 5 is worth giving up the final 5 of potential decay
- It keeps the position book clean — fewer positions to track

### Consequences of Close-at-5

**Scenario: PE at old strike closes at 5**
```
PE had 10 lots at strike 96,000, entry premium 98.
Premium drops to 5. Close at 5.
Realized profit: (98 - 5) × 10 = 930

PE total_lots decreases by 10.
If these were the only PE at 96,000 → remove strike from monitoring.
```

**Scenario: ALL CE positions close at 5 (CE fully gone)**
```
CE total_lots = 0. No CE position exists.

If the algo later needs to SELL CE to hedge PE losses:
  → The algo has no active CE strike
  → Treat this as a STRIKE SHIFT for CE:
    1. Query the options chain
    2. Find a CE strike with premium ≥ shift_threshold
    3. Sell CE lots at the new strike
    4. Set active_ce_strike to the new strike
    5. Continue normally
```

**Scenario: BOTH sides fully closed at 5**
```
CE total_lots = 0, PE total_lots = 0
All premium is locked in as realized profit.
Strategy is COMPLETE. Best possible outcome.
strategy_status = "STOPPED"
```

### Close-at-5 Threshold is Configurable

The user can set this to any value (e.g., 3, 5, 10) via WebUI. Value of 5 is the default. Setting it to 0 effectively disables this feature (positions expire naturally).

### 11.1 Elevated Close-at-5 During Wind-Down (Added Feb 17, 2026)

When wind-down mode is active (see §4.2), the close-at-5 threshold is elevated to close positions more aggressively:

```
IF wind_down_active:
    elevated_threshold = entry_premium × (wind_down_threshold_pct / 100)
    → Example: entry at 100, wind_down_threshold_pct = 25%
    → Close if premium ≤ 25 (instead of default 5)

Positions are closed in LIFO order (most recently added first).
```

This allows the algo to lock in profits earlier during the final hours, when theta decay is rapid and the position has captured most of its value.

---

## SECTION 12: MULTI-REVERSAL CYCLES

In an oscillating market, the algo handles multiple direction changes:

### Cycle 1: Market Goes UP
- CE is aggressor → sell extra PE lots
- PE adjustment lots accumulate
- CE adjustment lots: 0
- last_aggressor: CE

### Cycle 2: Market Reverses DOWN
- First reversal → compute PE adjustment P&L (all PE adj fills, including frozen if shifted)
- If PE adjustments underwater → sell CE lots
- After first reversal → standard mode: all active PE lots × incremental move
- CE adjustment lots accumulate
- last_aggressor: PE

### Cycle 3: Market Reverses UP AGAIN
- First reversal → compute CE adjustment P&L (all CE adj fills)
- CE adjustments went underwater → sell PE lots
- After first reversal → standard mode
- PE adjustment lots grow further
- last_aggressor: CE

### The Rule For Any Reversal

```
Side X is now the aggressor.

IF X has adjustment positions (from prior hedging of the other side):
    → Compute actual P&L of ALL X adjustment fills (active + frozen)
    → If P&L < 0: loss_to_cover = abs(P&L). Sell opposite side.
    → If P&L ≥ 0: do nothing (adjustments still profitable)

IF X has NO adjustment positions:
    → Standard formula: loss = (X_now - trigger) × active_lots

After each adjustment on the new side:
    → Update triggers
    → All subsequent checks use standard formula
```

### Adjustment Average Across Reversals

When computing adjustment P&L, ALL prior adjustment fills on that side are included — from every prior cycle. The P&L is computed per-fill using each fill's actual strike and current premium:

```
for each fill:
    current = fetch_premium(fill.strike)
    pnl += (fill.entry_premium - current) × fill.lots
```

This is accurate regardless of how many cycles have occurred or how many strike shifts happened.

---

## SECTION 13: SAFETY MECHANISMS

### 13.1 — Position Cap

```
IF opposing_total_lots + lots_to_sell > max_lots_per_side:
    → Reduce lots to fit within cap
    → If no room left: ALERT user, skip adjustment
    → User can raise cap via WebUI if they choose
```

### 13.2 — Maximum Adjustments

```
IF adjustment_count ≥ max_adjustments:
    → STOP adjusting. Alert user.
    → User can raise limit via WebUI
```

### 13.3 — Maximum Loss (Hard Stop)

Computed every interval:
```
unrealized_pnl = 0
for each open position (active + shifted, across ALL strikes):
    current = fetch_premium(position.strike, position.type)
    unrealized_pnl += (position.entry_premium - current) × position.lots

total_pnl = realized_pnl + unrealized_pnl

IF total_pnl < -max_loss_amount:
    → CLOSE ALL POSITIONS immediately (buy back everything)
    → strategy_status = "STOPPED"
    → Alert user: "Max loss of {max_loss_amount} breached. All positions closed."
```

### 13.4 — Whipsaw Detection

```
IF adjustment_count ≥ 3:
    last_3 = adjustment_history[-3:]
    sides = [a.side for a in last_3]
    
    IF sides alternate (CE,PE,CE) or (PE,CE,PE):
        → PAUSE algo
        → Alert: "Whipsaw detected. Market oscillating.
           Suggestion: increase interval or min_trigger_move."
        → User decides: resume, increase interval, or stop
```

### 13.5 — Position Asymmetry Warning

```
ratio = max(ce_total_lots, pe_total_lots) / min(ce_total_lots, pe_total_lots)

IF ratio > 3: WARNING on WebUI
IF ratio > 5: ALERT — strongly recommend pausing
```

### 13.6 — Near-Expiry Behavior

```
IF time_to_expiry < stop_adjustment_mins (default 15):
    → Stop all adjustments
    → Let theta decay finish the job
    → Show countdown on WebUI

IF time_to_expiry < auto_close_mins (default 5):
    → Close ALL remaining positions at market
    → Strategy complete
```

### 13.7 — Margin Check (Pre-Adjustment)

```
Before every sell order:
    available_margin = fetch_available_margin()
    required_margin = estimate_margin(lots_to_sell, strike, premium)
    
    IF required_margin > available_margin:
        → Reduce lots to what margin allows
        → If zero: ALERT "Insufficient margin"
```

### 13.8 — Circuit Breaker (Exchange API Fault Isolation)

Wraps all exchange API calls. 3 states: CLOSED (normal), OPEN (failing), HALF_OPEN (probing).

```
On API failure:
    failure_count += 1
    IF failure_count ≥ FAILURE_THRESHOLD (3):
        → State = OPEN
        → Partial beat: close-at-5 + safety only (cached prices)
        → After RESET_TIMEOUT (30s): State = HALF_OPEN, probe
        → Probe success: State = CLOSED
        → Probe failure: stay OPEN, emit mmm_safety event after 3 successive failures

NEVER terminates the session. Always self-healing.
```

### 13.9 — P&L Incomplete Guard

If more than 50% of premium fetch calls fail during a heartbeat:
```
_pnl_calculation_incomplete = True
→ Session PAUSED with reason "P&L calculation incomplete"
→ Perp hedge skips rebalance (stale-delta guard)
→ Emits mmm_safety event with type='calculation_incomplete'
→ Resumes automatically when fetch success rate recovers above 50%
```

### 13.10 — Position Cap Hard-Block

The position cap check (§13.1) action is `'stop_adjustments'` (not `'warn'`). When position cap is reached, adjustments are blocked — not merely warned.

### 13.11 — Decaying Peak P&L

The peak P&L for trailing stop uses exponential decay when P&L is below peak:
```
IF current_pnl > peak_pnl:
    peak_pnl = current_pnl          # New high water mark
ELSE:
    peak_pnl = 0.9 × peak_pnl + 0.1 × current_pnl   # Decay toward reality

On reversal:
    peak_pnl = current_pnl          # Hard reset
```

This prevents stale trailing stops from never firing (e.g., peak of $500 that decayed to $50 hours ago).

---

## SECTION 14: STRENGTH IMPROVEMENTS

### 14.1 — Premium Buffer

Sell slightly more lots than mathematically needed:

$$\text{lots\_to\_sell} = \left\lceil \frac{\text{loss\_to\_cover}}{\text{hedge\_premium}} \times (1 + \text{buffer\_pct}) \right\rceil$$

Default `buffer_pct = 0.05` (5%). This covers:
- Slippage between calculated price and actual fill
- Micro-moves within the interval that erode coverage
- The fact that ceil() alone sometimes provides barely any buffer

### 14.2 — Minimum Trigger Move

$$\text{triggered} = (\text{premium\_now} - \text{trigger}) > \text{min\_trigger\_move}$$

Default `min_trigger_move = 3`. Prevents triggering on ±1-2 oscillations around the trigger level.

### 14.3 — Cooldown After Reversal

When reversal detected, wait one extra interval before adjusting. This filters noise:
- If the spike reverses back → no unnecessary adjustment was made
- If it sustains → adjust on the next tick (loss is slightly larger but the direction is confirmed)

Default: enabled. Can be disabled by user.

### 14.4 — Net P&L Guardrail

Track total_pnl (realized + unrealized) every interval:

- **Warning:** total_pnl < -50% of initial premium collected
- **Pause:** total_pnl < -100% of initial premium collected  
- **Hard stop:** total_pnl < -max_loss_amount (absolute)

### 14.5 — Periodic Absolute P&L Reconciliation

Every 5 adjustments, compute the TRUE net P&L from scratch:

```
actual_pnl = realized_pnl
for each open position:
    actual_pnl += (entry_premium - current_premium) × lots

IF abs(actual_pnl - tracked_pnl) > reconciliation_threshold:
    → Log discrepancy
    → Correct tracked_pnl to actual_pnl
    → The absolute P&L is truth
```

This catches drift from rounding/overcoverage accumulation.

### 14.6 — Trailing Profit Protection

Once net P&L reaches a high-water mark, protect it:

```
IF total_pnl > peak_pnl:
    peak_pnl = total_pnl

IF total_pnl < peak_pnl × (1 - trailing_stop_pct):
    → Alert: "Profit declining from peak. Consider stopping."
    → Optionally auto-stop
```

Default `trailing_stop_pct = 0.5` (stop if profit drops to 50% of peak).

### 14.7 — Theta Acceleration (Late-Day Widening)

In the last 2-3 hours before expiry, theta decay is fastest. Both premiums are collapsing rapidly. The algo benefits from LESS intervention:

```
IF time_to_expiry < theta_acceleration_window (default 120 mins):
    base_trigger = min_trigger_move × 2
    effective_trigger = min(base_trigger, 80.0)    ← hard cap prevents trigger from becoming unreachable
    → Require bigger moves to trigger
    → Let theta do the work
```

### 14.8 — Decimal Arithmetic in P&L Accumulation

All P&L calculations use Python `Decimal` via a `_D(x)` helper:
```python
def _D(x) -> Decimal:
    return Decimal(str(x))    # str() avoids float→Decimal IEEE 754 artifact
```

Applied in: `realized_pnl += _D(entry) - _D(current) * _D(lots)`, `total_premium_collected`, `total_fees`, and all intermediate loss calculations in `mmm_engine.py`. Eliminates $0.50–$1.00 drift observed over full-day sessions with many adjustments.

### 14.9 — Unified Position Ledger

All positions (original, adjustment, frozen/shifted) stored in a single `positions[]` list per side. Benefits:
- Single source of truth — no divergence between separate arrays
- All derived counters (`active_lots`, `total_lots`, etc.) computed by `recompute_side_lots()`
- ID-based removal via `_pos_id` for O(1) operations (no index-based removal)
- Auto-migration adds `_pos_id` and `position_type` to legacy sessions
- 50+ read sites unchanged — they still read the same derived fields

### 14.10 — Trigger Snapshot Validation

Before `evaluate_triggers()`, the algo validates that the active strike key exists in the trigger snapshot:
```
IF active_strike NOT IN trigger_snapshot OR trigger_snapshot[active_strike] == 0:
    → Fetch current premium from exchange
    → Initialize trigger_snapshot[active_strike] = current_premium
    → Log "trigger snapshot initialized from exchange"
```

Prevents false trigger fires after session restart or strike shift.

### 14.11 — Re-evaluate After Close-at-5

When close-at-5 closes positions on the aggressor side, triggers are re-evaluated before processing adjustments:
```
IF close_at_5 closed any aggressor positions:
    → Re-compute ce_excess and pe_excess
    → If aggressor side no longer triggered → skip adjustment
```

Prevents over-hedging when close-at-5 already relieved directional pressure.

### 14.12 — Param Interdependency Validation

On hot-reload, validates parameter relationships:
```
wind_down_minutes ≥ close_at_5_threshold
margin tier thresholds in ascending order (GREEN < YELLOW < ORANGE < RED < CRITICAL)
max_adjustments ≥ whipsaw_limit
buffer_pct > 0 when auto-execution enabled
```

Rejects invalid parameter combinations with specific error messages.

---

## SECTION 15: BTC-SPECIFIC CONSIDERATIONS

### 15.1 — 24/7 Market

BTC options trade continuously. No market open/close, no overnight gaps from exchange hours. The algo runs around the clock until the expiry. User can set trading hours if they only want to be active during certain times (e.g., US session only).

### 15.2 — Available Expiries

Major exchanges (Deribit) offer:
- Daily expiries (0DTE)
- Weekly expiries
- Monthly / Quarterly expiries

0DTE options expire at 08:00 UTC daily. The algo should know the exact expiry time to calculate time_to_expiry correctly.

### 15.3 — Strike Intervals

BTC option strikes are typically at $500 or $1,000 intervals near ATM, wider further OTM. The algo must query the actual available strikes from the chain — not assume fixed intervals.

### 15.4 — Premium in USD vs BTC

On Deribit, BTC options are priced in BTC (e.g., 0.01 BTC) but the user thinks in USD. The algo should:
- Internally track premiums in whatever unit the exchange uses
- Display USD-equivalent on the WebUI for user clarity
- All calculations work regardless of denomination (the math is the same)

### 15.5 — Bid-Ask Spread

BTC options can have wide bid-ask spreads, especially OTM. When designing limit fills:
- Use **bid price** for selling (realistic worst-case fill estimate)
- Use **mark price** (mid) for trigger monitoring
- Use **ask price** for close-at-5 buying back

### 15.6 — Liquidity Check

Before selling at a strike (especially after a shift), verify:
```
IF bid_size at target strike < lots_to_sell:
    → Warning: low liquidity. Split order or choose different strike.
```

### 15.7 — No Gap Risk (But Volatility Spikes)

BTC doesn't have overnight gaps, but it has extreme volatility events (flash crashes, liquidation cascades). A 10-15% move in 30 minutes is possible. The safety mechanisms (max loss, position cap, margin check) are the defense against these.

### 15.8 — Funding and Fees

Each adjustment incurs trading fees. On 0DTE with frequent adjustments (every 5 min), this could be 40-50 trades/day. Account for fees in the P&L tracking:

```
total_fees = adjustment_count × fee_per_trade × avg_lots × lot_size
net_pnl = total_pnl - total_fees
```

---

## SECTION 16: COMPLETE WALK-THROUGH

### Scenario: UP → UP → SHIFT → REVERSAL → DOWN → RE-REVERSAL

Entry: BTC at 98,000. CE strike 100,000 (premium 100), PE strike 96,000 (premium 100), 10 lots each. shift_threshold = 50.

---

**T=0: ENTRY**
```
Sell 10 CE @ 100,000 strike, premium 100
Sell 10 PE @ 96,000 strike, premium 100

CE: active_strike=100000, active_lots=10, trigger_snapshot={100000: 100}
PE: active_strike=96000,  active_lots=10, trigger_snapshot={96000: 100}
last_aggressor = "NONE"
Total premium = 2000
```

---

**T+5: BTC at 99,000 | CE=130, PE=72**
```
CE(130) > trigger(100) + min_move(3)? YES → CE aggressor
PE(72) > trigger(100)? NO

Reversal? NONE→CE = No. First-ever adjustment.
Loss = (130 - 100) × 10 = 300

PE at 96,000 = 72 ≥ shift_threshold(50) → sell at active strike
Lots = ceil(300 / 72) = ceil(4.17) = 5
Sell 5 PE @ 96,000 at 72. Premium = 360.

State:
  CE: trigger=130, active_lots=10
  PE: trigger=72, active_lots=15 (10 orig + 5 adj)
  PE adj: [5@72], avg=72
  last_aggressor = "CE"
  adjustment_count = 1
  Total premium = 2360
```

---

**T+10: BTC at 100,500 | CE=190, PE=40**
```
CE(190) > trigger(130) + 3? YES → CE aggressor
PE(40) > trigger(72)? NO

Continuation (CE→CE).
Loss = (190 - 130) × 10 = 600

PE at 96,000 = 40 < shift_threshold(50) → STRIKE SHIFT!

Scan chain: PE at 98,000 has premium 110.
Shift: freeze PE at 96,000 (15 lots), new active PE at 98,000.
Sell at 98,000: ceil(600 / 110) = ceil(5.45) = 6 lots
Sell 6 PE @ 98,000 at 110. Premium = 660.

State:
  CE: trigger=190, active_lots=10
  PE: active_strike=98000, active_lots=6
      frozen: 15 lots at 96,000 (orig 10@100 + adj 5@72)
      total_lots=21
  PE adj at 98,000: [6@110], avg=110
  last_aggressor = "CE"
  adjustment_count = 2
  Total premium = 3020
```

---

**T+15: BTC at 100,200 | CE@100,000=170, PE@98,000=125, PE@96,000=35**
```
CE(170) > trigger(190)? NO
PE active(125) > trigger(110)? YES → PE aggressor

Reversal? last was "CE", now "PE" → YES, first reversal!

Compute PE adjustment P&L (all adjustment fills):
  PE 5@72 at strike 96,000: current prem=35 → pnl = (72-35)×5 = +185
  PE 6@110 at strike 98,000: current prem=125 → pnl = (110-125)×6 = -90
  Total adjustment pnl = 185 - 90 = +95

adjustment_pnl ≥ 0 → adjustments still profitable → DO NOTHING

Meanwhile, check close-at-5:
  PE@96,000 prem=35 → above 5, keep.

No action this interval. ✓
```

---

**T+20: BTC at 99,500 | CE@100,000=140, PE@98,000=160, PE@96,000=50**
```
CE(140) > trigger(190)? NO
PE active at 98,000(160) > trigger(110)? YES → PE aggressor

Still reversal context (last was "CE", PE is aggressor, first adj not done yet).

PE adjustment P&L:
  PE 5@72 at 96,000: current=50 → pnl = (72-50)×5 = +110
  PE 6@110 at 98,000: current=160 → pnl = (110-160)×6 = -300
  Total adjustment pnl = 110 - 300 = -190

adjustment_pnl < 0 → TRIGGERED. loss_to_cover = 190.

CE at 100,000 = 140 ≥ shift_threshold? YES (140 ≥ 50)
Lots = ceil(190 / 140) = ceil(1.36) = 2
Sell 2 CE @ 100,000 at 140. Premium = 280.

State:
  CE: active_strike=100000, active_lots=12 (10 orig + 2 adj)
      CE adj: [2@140], avg=140
      trigger_snapshot[100000] = 140
  PE: active_strike=98000, trigger_snapshot[98000]=160
      frozen: 15 lots at 96,000
  last_aggressor = "PE"
  adjustment_count = 3
  Total premium = 3300
```

---

**T+25: BTC at 98,800 | CE@100,000=110, PE@98,000=190, PE@96,000=65**
```
CE(110) > trigger(140)? NO
PE active(190) > trigger(160)? YES → PE aggressor

NOT first reversal (already did one at T+20). Standard formula (Case A).
Active loss = (190 - 160) × 6 = 180
Shifted loss: PE@96,000 has 15 lots, entry premiums avg ~89, current=65 → (65-89)<0 → no loss
Total loss = 180 + 0 = 180   ← shifted positions checked but not losing here

CE at 100,000 = 110 ≥ 50 → sell at active strike
Lots = ceil(180 / 110) = ceil(1.64) = 2
Sell 2 CE @ 100,000 at 110. Premium = 220.

State:
  CE: active_lots=14 (10 orig + 4 adj), CE adj: [2@140, 2@110], avg=125
      trigger=110
  PE: trigger=190
  last_aggressor = "PE"
  adjustment_count = 4
  Total premium = 3520
```

---

**T+30: BTC at 99,200 | CE@100,000=130, PE@98,000=170, PE@96,000=55**
```
CE(130) > trigger(110)? YES → CE aggressor
PE(170) > trigger(190)? NO

Reversal? last was "PE", now "CE" → YES, first reversal!

CE adjustment P&L:
  CE 2@140 at 100,000: current=130 → pnl = (140-130)×2 = +20
  CE 2@110 at 100,000: current=130 → pnl = (110-130)×2 = -40
  Total adjustment pnl = 20 - 40 = -20

adjustment_pnl < 0 → TRIGGERED. loss_to_cover = 20.

PE at 98,000 = 170 ≥ 50 → sell at active strike
Lots = ceil(20 / 170) = ceil(0.12) = 1
Sell 1 PE @ 98,000 at 170. Premium = 170.
Overcoverage: 170 - 20 = 150 (large buffer!)

State:
  CE: trigger=130
  PE: active_lots=7 at 98,000, PE adj at 98000: [6@110, 1@170], avg=(660+170)/7=118.57
      frozen: 15 at 96,000, total_lots=22
      trigger=170
  last_aggressor = "CE"
  adjustment_count = 5
  Total premium = 3690
```

---

**T+35: Close-at-5 triggers**
```
PE@96,000 premium = 4 → ≤ 5 → CLOSE

Buy back 15 PE lots at 96,000 @ premium 4.
Realized P&L from these positions:
  10 lots entry@100: (100-4)×10 = +960
  5 lots entry@72:   (72-4)×5  = +340
  Total realized = +1300

PE frozen_lots at 96,000 = 0 (all closed)
PE total_lots = 7 (active at 98,000 only)

realized_pnl += 1300
```

---

### Walk-Through Summary

| Time | BTC | CE Prem | PE Active Prem | Action | Lots Sold | Cum CE | Cum PE | Premium |
|------|---------|---------|----------------|--------|-----------|--------|--------|---------|
| T=0  | 98,000  | 100     | 100            | Entry  | 10+10     | 10     | 10     | 2000    |
| T+5  | 99,000  | 130     | 72             | Sell PE | 5        | 10     | 15     | 2360    |
| T+10 | 100,500 | 190     | 40→SHIFT→110   | SHIFT+Sell PE | 6 | 10     | 21     | 3020    |
| T+15 | 100,200 | 170     | 125            | NONE (adj +95) | — | 10     | 21     | 3020    |
| T+20 | 99,500  | 140     | 160            | Rev→Sell CE | 2    | 12     | 21     | 3300    |
| T+25 | 98,800  | 110     | 190            | Sell CE | 2       | 14     | 21     | 3520    |
| T+30 | 99,200  | 130     | 170            | Rev→Sell PE | 1   | 14     | 22     | 3690    |
| T+35 | —       | —       | PE@96k=4       | Close15 PE | —      | 14     | 7      | 3690+1300 realized |

**Final state:**
- CE: 14 lots at strike 100,000
- PE: 7 lots at strike 98,000 (active)
- Total premium collected: 3690
- Realized P&L (from close-at-5): +1300
- Total lots: 21 (from initial 20)
- Adjustments: 5
- Demonstrated: uptrend, strike shift, reversal, continuation, re-reversal, close-at-5

> **Note:** If perp_hedge_enabled=true during this scenario, the perp hedge would have opened a SHORT BTCUSD position around T+10 (when portfolio delta exceeded threshold due to BTC rising) and flipped to LONG around T+20 (when the reversal shifted delta). The perp P&L would partially offset the option adjustment losses from the BTC move, reducing the need for as many adjustment lots. See §23.7 for a detailed perp hedge walk-through.

---

## SECTION 17: DECISION TREE (Quick Reference)

```
EVERY INTERVAL:
│
├─ Fetch CE_now, PE_now at active strikes (via Circuit Breaker §13.8)
│     └─ If >50% fail → PAUSE (_pnl_calculation_incomplete)
├─ Run CLOSE-AT-5 on all positions
│     └─ If wind-down active → use elevated threshold (§11.1)
├─ Run SAFETY CHECKS (§13)
│     ├─ Max loss breached?         → CLOSE ALL, STOP
│     ├─ Position cap reached?      → HARD BLOCK adjustments
│     ├─ Max adjustments reached?   → ALERT, skip
│     ├─ Near expiry?               → STOP adjustments / AUTO-CLOSE
│     ├─ Whipsaw detected?          → PAUSE, alert
│     ├─ Trailing profit drop?      → ALERT (decaying peak)
│     └─ Margin insufficient?       → Reduce lots / skip
├─ Run REGIME CHECKS (§24)
│     ├─ Vol regime HIGH?           → BLOCK adjustments
│     ├─ Gamma HARD/EMERGENCY?      → BLOCK / EMERGENCY
│     └─ Trend detected?            → BLOCK adjustments
├─ Run MARGIN GUARDIAN (§25)
│     ├─ YELLOW?                    → WARN, block new sells
│     ├─ ORANGE?                    → Trigger wind-down
│     ├─ RED?                       → Emergency close
│     └─ CRITICAL?                  → Session STOP
│
├─ CE triggered? ─── PE triggered?
│     │                    │
│   YES                  YES → BOTH SIDES UP → Alert user, PAUSE (Section 8)
│     │                    │
│   YES                   NO → CE IS AGGRESSOR
│     │                        │
│     │                        ├─ Reversal? (last was PE)
│     │                        │   YES → Compute CE adj P&L
│     │                        │         └─ If < 0: hedge loss by selling PE
│     │                        │         └─ If ≥ 0: do nothing
│     │                        │
│     │                        │   NO → Standard: loss = active_loss + shifted_loss (ALL positions)
│     │                        │         └─ Hedge by selling PE
│     │                        │
│     │                        ├─ PE premium at active strike ≥ shift_threshold?
│     │                        │   YES → sell at active PE strike
│     │                        │   NO  → STRIKE SHIFT, then sell at new strike
│     │                        │
│     │                        └─ Sell lots, update triggers, update state
│     │
│    NO ─── PE triggered?
│              │
│            YES → PE IS AGGRESSOR (mirror of above, CE↔PE swapped)
│              │
│             NO → DO NOTHING (both in safe zone)
│
├─ Run PERP HEDGE (§23) if enabled
│     ├─ Calculate portfolio delta across ALL positions
│     ├─ |delta| > threshold?  → Rebalance/open perp position
│     ├─ Drift > band?         → Rebalance existing position
│     └─ Direction flip needed? → Atomic close + open opposite
│
└─ Emit WebSocket events, record heartbeat health
```

---

## SECTION 18: FORMULARY

### Standard Loss (Continuation or Post-First-Reversal)
$$L_{\text{active}} = (P_{\text{now}} - P_{\text{trigger}}) \times N_{\text{active}}$$
$$L_{\text{shifted}} = \sum_{j \in \text{shifted}} \max\bigl((P_{\text{current},j} - P_{\text{entry},j}) \times N_j, \; 0\bigr)$$
$$L = L_{\text{active}} + L_{\text{shifted}}$$

All positions (active + shifted at old strikes) contribute to total loss. No position is excluded.

### First-Reversal Loss (Generalized, Multi-Strike Safe)
$$L = \left| \sum_{i \in \text{adj fills}} (P_{\text{entry},i} - P_{\text{current at strike}_i}) \times N_i \right|$$

Only triggers when the sum is negative (adjustments underwater).

### Lots to Sell
$$N_{\text{sell}} = \left\lceil \frac{L}{P_{\text{hedge}}} \times (1 + \text{buffer\_pct}) \right\rceil$$

### Weighted Average of Adjustment Fills (Single Strike)
$$\bar{P}_{\text{adj}} = \frac{\sum_{i} N_i \cdot P_i}{\sum_{i} N_i}$$

### Premium Collected Per Adjustment
$$\text{Premium} = N_{\text{sell}} \times P_{\text{hedge}}$$

### Overcoverage (Buffer)
$$\text{Buffer} = (N_{\text{sell}} \times P_{\text{hedge}}) - L$$

### Net Mark-to-Market P&L
$$\text{Unrealized} = \sum_{\text{all open}} (P_{\text{entry},i} - P_{\text{current},i}) \times N_i$$
$$\text{Total P\&L} = \text{Realized} + \text{Unrealized}$$

### Position Asymmetry Ratio
$$R = \frac{\max(N_{\text{CE}}, N_{\text{PE}})}{\min(N_{\text{CE}}, N_{\text{PE}})}$$

### Portfolio Delta (for Perp Hedge)
$$\delta_{\text{portfolio}} = \sum_{i \in \text{all positions}} \delta_i \times N_i \times \text{LOT\_SIZE\_BTC} \times (-1)$$

### Effective Delta (with Perp Position)
$$\delta_{\text{effective}} = \delta_{\text{portfolio}} + \text{perp\_lots} \times \text{LOT\_SIZE\_BTC} \times \text{dir\_sign}$$

### Target Perp Lots
$$N_{\text{perp}} = \min\left(\left\lfloor \frac{|\delta_{\text{portfolio}}| \times \text{ratio}}{\text{LOT\_SIZE\_BTC}} + 0.5 \right\rfloor, \; N_{\text{max}}\right)$$

### Margin Utilization
$$U = \frac{M_{\text{position}} + M_{\text{order}}}{E_{\text{net}}} \times 100\%$$

---

## SECTION 19: USER PARAMETERS

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `desired_ce_premium` | Target CE premium for strike selection | User input | No (entry only) |
| `desired_pe_premium` | Target PE premium for strike selection | User input | No (entry only) |
| `initial_lots` | Starting lots per side | User input | No (entry only) |
| `expiry` | Target expiry | User input | No (entry only) |
| `adjustment_interval` | Seconds between checks | 300 | **Yes** |
| `min_trigger_move_pct` | Minimum % move above trigger to fire | 3% | **Yes** |
| `shift_threshold` | Min premium to sell at current strike | 50 | **Yes** |
| `shift_target_premium` | Target premium when selecting new strike after shift | 100 | **Yes** |
| `close_at_threshold` | Close positions at this premium or below | 5 | **Yes** |
| `premium_buffer_pct` | Extra lots % for slippage protection | 5% | **Yes** |
| `max_lots_per_side` | Maximum total lots per CE or PE | 100 | **Yes** |
| `max_adjustments` | Maximum number of adjustment events | 30 | **Yes** |
| `max_loss_amount` | Hard stop P&L threshold | User-defined | **Yes** |
| `stop_adjustment_mins` | Stop adjusting N mins before expiry | 15 | **Yes** |
| `auto_close_mins` | Auto-close all N mins before expiry | 5 | **Yes** |
| `cooldown_on_reversal` | Skip 1 interval on reversal | true | **Yes** |
| `whipsaw_limit` | Max alternating adjustments before pause | 3 | **Yes** |
| `trailing_stop_pct` | Protect profit at N% of peak | 50% | **Yes** |

**Adaptive Interval Parameters (Added Feb 17, 2026):**

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `adaptive_interval_enabled` | Enable/disable adaptive heartbeat interval | true | **Yes** |
| `adaptive_max_interval` | Maximum seconds between heartbeats when premiums are far | 1200 | **Yes** |

**Wind-Down Parameters (Added Feb 17, 2026):**

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `wind_down_enabled` | Enable/disable wind-down mode | true | **Yes** |
| `wind_down_minutes` | Minutes before expiry to activate wind-down | 120 | **Yes** |
| `wind_down_threshold_pct` | Close positions at ≤ N% of entry premium during wind-down | 25 | **Yes** |
| `wind_down_floor_action` | Action when wind-down can't close: close_all / stop_adjustments / alert | stop_adjustments | **Yes** |

All "Hot Reload = Yes" parameters can be changed via WebUI while the algo is running, and take effect on the next interval.

**Regime Control Parameters (Added Feb 20, 2026):**

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `regime_vol_enabled` | Enable volatility regime filter | true | **Yes** |
| `regime_vol_elevated_threshold` | IV percentile for ELEVATED state | 70 | **Yes** |
| `regime_vol_high_threshold` | IV percentile for HIGH state (blocks adjustments) | 90 | **Yes** |
| `regime_gamma_enabled` | Enable portfolio gamma cap | true | **Yes** |
| `regime_gamma_soft_cap` | Gamma level for SOFT state (warn) | 0.001 | **Yes** |
| `regime_gamma_hard_cap` | Gamma level for HARD state (block) | 0.003 | **Yes** |
| `regime_gamma_emergency` | Gamma level for EMERGENCY (close all) | 0.005 | **Yes** |
| `regime_trend_enabled` | Enable trend detection guard | true | **Yes** |
| `regime_trend_window_minutes` | Lookback window for trend calculation | 30 | **Yes** |
| `regime_trend_threshold_pct` | BTC move % to classify as trending | 2.0 | **Yes** |

**Margin Guardian Parameters (Added Feb 20, 2026):**

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `margin_guardian_enabled` | Enable real-time margin monitoring | true | **Yes** |
| `margin_yellow_pct` | Utilization % for YELLOW tier (warn) | 60 | **Yes** |
| `margin_orange_pct` | Utilization % for ORANGE tier (wind-down) | 75 | **Yes** |
| `margin_red_pct` | Utilization % for RED tier (emergency close) | 85 | **Yes** |
| `margin_critical_pct` | Utilization % for CRITICAL tier (session stop) | 95 | **Yes** |

**Perpetual Futures Delta Hedge Parameters (Added Feb 22, 2026):**

| Parameter | What It Controls | Default | Hot Reload? |
|-----------|-----------------|---------|-------------|
| `perp_hedge_enabled` | Enable/disable perp delta hedging | false | **Yes** |
| `perp_hedge_delta_threshold` | Min |delta| to trigger hedge action | 0.02 | **Yes** |
| `perp_hedge_ratio` | Fraction of delta to hedge (1.0 = full) | 1.0 | **Yes** |
| `perp_hedge_rebalance_band` | Drift from target before rebalancing | 0.005 | **Yes** |
| `perp_hedge_max_lots` | Maximum perp position lots | 50 | **Yes** |
| `perp_hedge_cooldown_sec` | Seconds between perp trades | 30 | **Yes** |

---

## SECTION 20: EDGE CASES

### 20.1 — CE and PE Entry Premiums Are Not Equal

The algo does NOT assume equal entry premiums. Each side has its own trigger and tracking. If CE is sold at 120 and PE at 80, the triggers are independently set. All formulas work regardless.

### 20.2 — Multiple Strike Shifts on Same Side

If BTC trends strongly, PE might get shifted 2-3 times:
- PE at 96,000 → shifted (15 lots, fully tracked)
- PE at 98,000 → shifted (8 lots, fully tracked)
- PE at 99,000 → active (3 lots)

Each shift moves the previous active to `shifted_positions`. ALL shifted positions at ALL old strikes remain fully tracked and are included in every loss calculation. The standard formula computes `active_loss + shifted_loss` where each shifted position is evaluated at its current live premium.

### 20.3 — No Available Strike for Shift

If no strike on the options chain has premium ≥ shift_threshold:
```
→ ALERT user: "No suitable strike for hedging. Premiums too low across all strikes."
→ Options: reduce shift_threshold, accept unhedged risk, or close positions
```

### 20.4 — User Manually Adjusts Mid-Strategy

User wants to add/remove lots via WebUI:
- **Add lots:** Record as new fills. Update active_lots, triggers.
- **Remove lots:** Close specified lots at market. Update active_lots, realized_pnl.

The algo treats user changes as if they were its own actions and continues from the updated state.

### 20.5 — Exchange API Downtime

If the exchange API is unreachable:
```
→ Retry 3 times with exponential backoff
→ If still down: PAUSE strategy, alert user
→ When API recovers: resume and immediately check all positions
```

### 20.6 — Extreme Move (Flash Crash / Spike)

BTC drops 15% in 5 minutes. CE collapses to 2, PE explodes to 500.

The algo's response depends on which safety mechanism fires first:
1. Max loss → CLOSE ALL
2. Position cap → Can't sell enough CE lots at premium 2 → ALERT
3. Close-at-5 → CE closed automatically
4. Strike shift → finds new CE strike, but loss is enormous → max_loss likely fires first

**This is the scenario where max_loss_amount is the last line of defense.** Without it, the algo would try to sell 250+ lots of CE at premium 2, which is catastrophic.

---

## SECTION 21: WHY THIS LOGIC IS FLAWLESS

1. **Universal trigger system** — both triggers always update to current prices after every adjustment. One rule, no exceptions.

2. **First-reversal uses actual adjustment P&L** — computes per-fill, per-strike, exact to the penny. No averaging approximations when strikes differ.

3. **After first reversal → standard formula includes ALL positions** — active_loss + shifted_loss. Every open position at every strike is evaluated at its current live premium. No position is ever excluded from loss calculations.

4. **Ceiling rounds always protect** — overcoverage is a feature, never under-hedged. Premium buffer adds explicit safety margin.

5. **Strike shifting prevents lot explosion** — instead of selling 50 lots at premium 3, sell 2 lots at premium 120 at a closer strike. Same coverage, 96% fewer new lots. Shifted positions remain fully tracked.

6. **Close-at-5 locks profit and cleans state** — positions that have given 95%+ of their profit are closed. Reduces complexity and frees margin.

7. **Both-sides-up = user decides** — the algo does NOT auto-act in the most dangerous scenario. Human judgment prevails.

8. **Auto-initialization from desired premium** — user doesn't need to know strikes. Just say "I want ~100 premium" and the algo finds the right strike.

9. **Multi-strike P&L is computed per-fill** — never averages across different strikes. Each fill's P&L is computed at its own strike's current premium.

10. **Safety at every layer** — min premium guard, position cap, max loss, margin check, whipsaw detection, near-expiry shutdown, trailing profit protection, and asymmetry alerts.

11. **BTC 24/7 native** — no market-hours assumptions, no gap-risk logic needed. Continuous monitoring from entry to expiry.

12. **Every parameter is hot-reloadable** — user can adjust shift_threshold, interval, min_trigger_move, and all safety limits without restarting.

13. **Complete walk-through verified** — Section 16 traces 7 intervals covering up-trend, strike shift, reversal (with adjustment P&L ≥0 skip), continuation, re-reversal, and close-at-5.

14. **Decimal arithmetic eliminates P&L drift** — All accumulation paths use `Decimal` through `str(x)` conversion. No IEEE 754 artifacts.

15. **Unified Position Ledger** — Single `positions[]` list per side with ID-based removal. All computed views derived by `recompute_side_lots()`. No divergence possible.

16. **Perpetual futures hedge complements options** — Perps absorb directional risk (delta) while options collect theta. Institutional approach: two independent systems working simultaneously.

17. **Regime controls pre-filter adjustments** — Vol/gamma/trend checks prevent selling into adverse conditions. But never force-close existing positions (that's the margin guardian's job).

18. **Margin guardian enforces real exchange limits** — Tier-based escalation from warn to session-stop. Uses actual exchange margin data, not estimates.

19. **Circuit breaker isolates API failures** — Never terminates the session. Self-heals after 30 seconds. Graduated partial-beat or full-skip.

---

---

## SECTION 22: WEBUI MONITORING PANELS (Added Feb 18, 2026)

The WebUI provides 12 detail tabs for each session. The following are the monitoring panels relevant to the calculation logic:

### 22.1 Positions Tab (Tab 1)

Shows every individual fill as a separate row:
- Original entry positions (CE + PE)
- Each adjustment fill as its own row (Adj #1, Adj #2, etc.)
- Frozen positions at old strikes after shifts (with ❄️ icon)
- Per-row P&L: `(entry_premium - current_premium) × lots × LOT_SIZE_BTC`
- Current premium resolved from heartbeat `premium_map` (4-source priority)

### 22.2 Consolidated Positions Tab (Tab 8)

Groups all individual fills at the same (side, strike) into a single consolidated row:
- **Weighted average entry**: `Σ(lots_i × premium_i) / Σ(lots_i)` across original + adjustment + frozen fills
- **Total lots**: sum of all fills at that strike
- **Notional BTC**: total_lots × LOT_SIZE_BTC (0.001)
- **Aggregated P&L**: sum of P&L across all fills at that strike
- **Fill count breakdown**: tooltip showing how many original/adjustment/frozen lots

This is purely a frontend aggregation — same data as Positions Tab, grouped differently.

### 22.3 Greeks & IV Tab (Tab 9)

Fetches live Greeks and Implied Volatility from Delta Exchange `/v2/tickers/{symbol}` for each unique (strike, option_type) in the session:

| Greek | What It Means for MMM (Short Sellers) |
|-------|--------------------------------------|
| Delta (δ) | Premium change per $1 BTC move. Short calls: lose when BTC rises. Short puts: lose when BTC drops. |
| Gamma (γ) | Rate of change of delta. High gamma near expiry = risk of rapid delta changes. |
| Theta (θ) | Time decay per day. **As sellers, theta works IN YOUR FAVOR** — premiums decay toward zero. |
| Vega (ν) | Sensitivity to IV changes. IV spike = premiums rise = bad for sellers. |
| Mark IV | Market consensus implied volatility for the option. |
| Bid/Ask IV | IV at best bid and ask — IV spread. |

**Portfolio totals**: Position-weighted sums (lots × per-contract greek) across all positions.

**Auto-refreshes** every 60 seconds via backend API.

> **IMPORTANT NOTE ON SIGN CONVENTION:** The Greeks shown are raw option Greeks from the exchange. For SHORT positions (which MMM exclusively holds), the position-level exposure is the NEGATIVE of displayed values. E.g., if theta shows -332, the seller's actual theta exposure is +332 (earning $332/day of decay). See Section 22.4.

### 22.4 Greek Sign Convention for Short Sellers

MMM sells options. The Delta Exchange API returns Greeks as if you are LONG the option. To interpret correctly for SHORT positions:

| Raw Greek | Short Position Meaning |
|-----------|----------------------|
| Delta +0.37 (CE) | Position delta = **-0.37** → you LOSE when BTC rises |
| Delta -0.10 (PE) | Position delta = **+0.10** → you LOSE when BTC drops |
| Theta -332 | Position theta = **+332** → you EARN $332/day from decay |
| Gamma +0.0003 | Position gamma = **-0.0003** → delta moves against you on big moves |
| Vega +11.38 | Position vega = **-11.38** → IV spike increases your loss |

The portfolio total delta sign tells you the net directional bias.

### 22.5 Perp Hedge Tab (Tab 14, Added Feb 22, 2026)

Shows the perpetual futures delta hedge state:
- Direction indicator: LONG / SHORT / FLAT
- Current lots, entry price, effective portfolio delta
- Unrealized and realized perp P&L
- Rebalance history and trade count
- Toggle button (enable/disable) and Close button (exit perp immediately)
- Delta threshold, ratio, rebalance band parameters displayed
- Updates via `mmm_perp_hedge_update`, `mmm_perp_hedge_execution`, `mmm_perp_hedge_flip` WebSocket events

### 22.6 Regime Tab (Tab 12, Added Feb 20, 2026)

Shows the three regime controls and their current states:
- Volatility: NORMAL / ELEVATED / HIGH — with IV percentile
- Gamma: NORMAL / SOFT / HARD / EMERGENCY — with portfolio gamma value
- Trend: NORMAL / TREND_UP / TREND_DOWN — with price change %
- Aggregate action badge: NORMAL / WARN / BLOCK / EMERGENCY
- Updates via `mmm_regime` WebSocket events

### 22.7 Margin Tab (Tab 13, Added Feb 20, 2026)

Shows real-time margin status from the exchange:
- Current tier badge (GREEN/YELLOW/ORANGE/RED/CRITICAL) with color coding
- Utilization percentage with progress bar
- Position margin, order margin, net equity values
- Tier threshold configuration
- Updates via heartbeat WebSocket

---

*This is the definitive calculation logic for Money Power. Every decision rule, formula, and edge case is documented. Covers 25 sections: core algorithm (§1-12), safety (§13), improvements (§14), BTC specifics (§15), walk-through (§16), reference (§17-18), parameters (§19), edge cases (§20), correctness (§21), WebUI (§22), perp hedge (§23), regime controls (§24), margin guardian (§25). Once sealed, this document drives the implementation directly — each section maps to a code module.*

---

## SECTION 23: PERPETUAL FUTURES DELTA HEDGE (Added Feb 22, 2026)

An optional delta-hedging layer using BTC perpetual futures (BTCUSD). Perps are linear instruments (zero gamma) — they absorb directional moves without adding gamma exposure.

### 23.1 Why Perp Hedging?

MMM sells both CE and PE, creating a short straddle/strangle. Near-ATM, the net delta can become significant:
- BTC rises → short calls lose, delta becomes negative
- BTC drops → short puts lose, delta becomes positive

Perp hedge neutralizes this directional risk, leaving only theta (time decay) as the primary source of income.

### 23.2 Delta Calculation

Every heartbeat (when perp_hedge_enabled):

$$\delta_{\text{portfolio}} = \sum_{i \in \text{all positions}} \delta_i \times N_i \times \text{LOT\_SIZE\_BTC} \times (-1)$$

The $\times (-1)$ accounts for SHORT positions (MMM only sells). Delta values ($\delta_i$) come from the exchange's live Greeks API.

$$\delta_{\text{effective}} = \delta_{\text{portfolio}} + \delta_{\text{perp\_position}}$$

Where $\delta_{\text{perp\_position}} = \text{perp\_lots} \times \text{LOT\_SIZE\_BTC} \times \text{direction\_sign}$ (LONG=+1, SHORT=-1, FLAT=0).

### 23.3 Hedge Decision Logic

```
IF |effective_delta| > perp_hedge_delta_threshold:
    target_delta = -portfolio_delta × perp_hedge_ratio
    target_lots = round(|target_delta| / LOT_SIZE_BTC)
    target_lots = min(target_lots, perp_hedge_max_lots)   ← cap
    target_direction = LONG if target_delta > 0 else SHORT
    
    IF target_direction ≠ current_direction:
        → Direction flip: close current → open opposite (atomic)
    ELIF |target_lots - current_lots| / current_lots > perp_hedge_rebalance_band:
        → Rebalance: adjust to target_lots
    ELSE:
        → Within band, no action
```

### 23.4 Safety Guards

| Guard | Behavior |
|-------|----------|
| Max lots cap | `target_lots = min(target_lots, perp_hedge_max_lots)` |
| Cooldown timer | No trade within `perp_hedge_cooldown_sec` of last trade |
| Stale delta | Skip hedge when `_pnl_calculation_incomplete` (>50% fetch failures) |
| Session stop | Auto-close perp position on max-loss, trailing stop, wind-down, manual stop |
| Orphan protection | On session stop, close perp even if options close fails |

### 23.5 P&L Inclusion

Perp P&L is included in the session total:
$$\text{total\_pnl} = \text{realized\_pnl} + \text{unrealized\_pnl} + \text{perp\_hedge.realized\_pnl} + \text{perp\_hedge.unrealized\_pnl}$$

This means max-loss and trailing-stop checks incorporate perp hedge results.

### 23.6 Interaction with MMM Adjustments

- Both systems run simultaneously (institutional approach)
- Adjustments collect theta via options; perp hedges delta
- Regime may block adjustments but NOT perp hedge — perp hedge IS the defense when regime blocks
- After an adjustment changes the position profile, the next heartbeat's delta calculation automatically reflects the change

### 23.7 Walk-Through: Perp Hedge in Action

```
T=0: Entry — 10 CE @ 100000, 10 PE @ 96000. perp_hedge_enabled=true.
     Portfolio delta = (-0.37 × 10 + 0.10 × 10) × 0.001 × (-1) = +0.0027
     |0.0027| > threshold(0.02)? NO → no hedge needed

T+5: BTC at 99,000 — CE delta=-0.50, PE delta=+0.05
     Portfolio delta = (-0.50×10 + 0.05×10) × 0.001 × (-1) = +0.0045
     |0.0045| > 0.02? NO → still within band

T+10: BTC at 100,500 — CE delta=-0.72, PE delta=+0.02
     Portfolio delta = (-0.72×10 + 0.02×10) × 0.001 × (-1) = +0.007
     Plus 6 new PE @ 98000 (delta=-0.15): +0.0009
     Total portfolio delta = +0.0079
     |0.0079| > 0.02? NO → still within band

T+20: BTC at 101,500 — CE delta=-0.88 (deep ITM)
     Portfolio delta = +0.025 (significant long bias from short calls)
     |0.025| > 0.02? YES → HEDGE!
     target = -0.025 × 1.0 = -0.025 (need to go SHORT perp)
     lots = round(0.025 / 0.001) = 25 lots SHORT BTCUSD
     → Place: SELL 25 BTCUSD perp
     effective_delta = 0.025 - 0.025 = ~0 ✔️

T+25: BTC reverses to 99,000 — CE delta=-0.30, PE delta=+0.25
     Portfolio delta = -0.020 (now short bias as calls lose ITM)
     Perp still SHORT 25 lots → effective_delta = -0.020 - 0.025 = -0.045
     |0.045| > 0.02? YES → DIRECTION FLIP!
     target = +0.020 × 1.0 = +0.020 (need to go LONG)
     lots = 20 lots LONG BTCUSD
     → Close SHORT 25 (realize P&L) → Open LONG 20
     effective_delta ≈ 0 ✔️
```

---

## SECTION 24: REGIME CONTROLS (Added Feb 20, 2026)

Pre-adjustment checks that block option sells during adverse market conditions. Three independent controls with an aggregate action.

### 24.1 Volatility Regime Filter

Monitors implied volatility of the underlying BTC options:

```
compute IV percentile from recent history

IF iv_percentile ≥ regime_vol_high_threshold (90):
    vol_state = HIGH → ACTION_BLOCK
ELIF iv_percentile ≥ regime_vol_elevated_threshold (70):
    vol_state = ELEVATED → ACTION_WARN
ELSE:
    vol_state = NORMAL → ACTION_NORMAL
```

**Rationale:** High IV means premiums are inflated by fear. Selling into an IV spike risks the spike continuing (vega risk). Better to wait for IV mean-reversion.

### 24.2 Portfolio Gamma Cap

Computes portfolio-level gamma exposure:

$$\gamma_{\text{portfolio}} = \sum_{i} |\gamma_i \times N_i \times \text{LOT\_SIZE\_BTC}|$$

```
IF gamma > regime_gamma_emergency (0.005):
    gamma_state = EMERGENCY → ACTION_EMERGENCY (close all)
ELIF gamma > regime_gamma_hard_cap (0.003):
    gamma_state = HARD → ACTION_BLOCK
ELIF gamma > regime_gamma_soft_cap (0.001):
    gamma_state = SOFT → ACTION_WARN
ELSE:
    gamma_state = NORMAL → ACTION_NORMAL
```

**Rationale:** High gamma near expiry means delta changes rapidly with small BTC moves. New adjustments add gamma and make the portfolio harder to manage.

### 24.3 Trend Detection Guard

Looks for sustained directional BTC moves:

```
price_change_pct = (btc_now - btc_N_minutes_ago) / btc_N_minutes_ago × 100

IF |price_change_pct| > regime_trend_threshold_pct (2.0):
    trend_state = TREND_UP or TREND_DOWN → ACTION_BLOCK
ELSE:
    trend_state = NORMAL → ACTION_NORMAL
```

**Rationale:** In a strong trend, adjustments compound losses because each new sell adds exposure in the wrong direction. Better to let the perp hedge absorb directionality.

### 24.4 Aggregate Action

```
aggregate = max(vol_action, gamma_action, trend_action)

ACTION_NORMAL    → proceed normally
ACTION_WARN      → emit mmm_regime event, proceed with caution
ACTION_BLOCK     → skip adjustment this heartbeat
ACTION_EMERGENCY → close all positions, stop session
```

**Key rule:** Regime controls block NEW adjustments but do NOT force-close existing options positions (that's the margin guardian's job). Close-at-5 and wind-down still run regardless.

**Perp hedge exception:** Perp hedge runs regardless of regime state. When regime blocks adjustments, the perp hedge is the primary defense.

---

## SECTION 25: MARGIN GUARDIAN (Added Feb 20, 2026)

Queries Delta Exchange for real-time margin utilization and enforces tier-based defense.

### 25.1 Margin Utilization Calculation

$$\text{utilization} = \frac{\text{position\_margin} + \text{order\_margin}}{\text{net\_equity}} \times 100\%$$

All values from the exchange's actual margin API (not estimated).

### 25.2 Tier Escalation

| Tier | Threshold | Action |
|------|-----------|--------|
| GREEN | < 60% | Normal operations |
| YELLOW | ≥ 60% | Warn, block new option sells |
| ORANGE | ≥ 75% | Trigger wind-down (close positions at elevated threshold) |
| RED | ≥ 85% | Emergency close (close positions at market) |
| CRITICAL | ≥ 95% | Session STOP (all positions closed, session terminated) |

Thresholds are user-configurable via hot-reload.

### 25.3 Tier Severity

```python
tier_severity = {GREEN: 0, YELLOW: 1, ORANGE: 2, RED: 3, CRITICAL: 4}
```

On tier escalation (severity increases), emits Telegram alert via `mmm_telegram.py`.

### 25.4 Interaction with Other Systems

- Margin guardian runs AFTER safety checks, BEFORE trigger evaluation
- At YELLOW+: blocks `mmm_executor.py` from placing new sell orders
- At ORANGE: triggers wind-down regardless of time to expiry
- At RED/CRITICAL: overrides all other logic — priority is capital preservation
