# Money Power Algorithm — Refined Master Plan

> **⚠️ HISTORICAL REFERENCE ONLY**
> This document is the original design plan. For the current authoritative
> technical reference that reflects actual code, see **[AI_MMM_CONTEXT.md](AI_MMM_CONTEXT.md)**.
> Discrepancies between this document and code should be resolved in favour of the code.

> **Strategy Type:** Options Selling with Dynamic Hedging via Incremental Shorts
> **Target:** 0DTE / any user-selected expiry
> **Core Idea:** Sell CE + PE, continuously hedge the losing side by selling more of the winning (decaying) side
> **Architecture:** Extends existing `BaseStrategy` → new `MoneyPowerStrategy` class  

---

## 1. LOGICAL ERRORS FOUND IN ORIGINAL SPEC

### Error #1: Wrong Average Price for Additional PE Positions ❌

**Original document states:**
> "average price of the additional PE position, which is 84.28"

**Actual calculation:**
- Additional PE positions: 3 lots @ 80, 2 lots @ 70, 2 lots @ 60
- Weighted average = (80×3 + 70×2 + 60×2) / (3+2+2) = (240+140+120) / 7 = **500/7 = 71.43**

**84.28 is mathematically wrong.** The correct additional-PE average is **71.43**.

This matters because 71.43 means the reversal trigger fires LATER (PE must reach 71.43+ instead of 84.28), giving MORE room before the algo starts hedging the reverse direction. Using 84.28 would trigger hedging too early, burning unnecessary lots.

---

### Error #2: Inconsistent Loss Calculation on Reversal

When the market reverses (PE rises to 100), the document calculates:
> `additional PE position loss = (100 - 84.28) * 7 = 115.96`

With the corrected average (71.43), this should be:
> `additional PE position loss = (100 - 71.43) * 7 = 200`

This is a **significantly larger loss** than what was calculated, meaning you'd need more CE lots to cover it. The original spec underestimates the reversal hedge requirement.

---

### Error #3: Missing the "New Incremental Loss" Concept in the First Reversal

When CE originally went from 100→120→130→140, the algo correctly only hedges the **incremental** loss each interval (the delta between the last-checked price and the current price).

But on the first reversal (PE at 100), the document computes loss from PE's sold-average (71.43) to current price (100). This is correct for the FIRST reversal check, but the algo should then set the "last-adjusted PE price" to 100 for subsequent checks — which it DOES do in the follow-up examples. So the pattern is correct but **the initial trigger and loss amount were wrong due to Error #1**.

---

### Error #4: Reversal Trigger Only Watches Additional Positions

The document says: "the algo will trigger the adjustment only when PE price is above the average price of the additional PE position."

This is WRONG for prolonged reversals. Once PE exceeds the original entry price (100), the ORIGINAL PE position is also losing money. The document actually handles this correctly in the later examples (adds original PE loss to additional PE loss), but the **trigger rule** should be stated as:

> **Trigger on reversal = PE price > min(original PE entry, additional PE average)**

Since the additional positions are always sold at lower prices than the original, this effectively means: **trigger when PE > additional PE average** (which is always less than the original entry). So the threshold is correct, but for the wrong reason. It works by accident. The refined logic below makes this explicit.

---

### Error #5: No Accounting for Transaction Costs

Each adjustment sells more lots. With frequent adjustments (every 5 mins on 0DTE), you could execute 40-50 orders in a trading session. Transaction costs/slippage eat into the premium collected and are not factored.

---

## 2. CRITICAL RISKS IDENTIFIED

### Risk A: Exponential Position Growth (THE KILLER)

This is the **most dangerous** aspect. In a trending market:
- Each interval, the losing side's price increases → more lots needed
- The winning side's premium DECREASES (goes further OTM) → even MORE lots needed per unit of loss
- Total lots grow **super-linearly**

**Example of explosion:**
| Interval | CE Price | PE Price | New PE Lots Sold | Total PE Lots | Total Short Exposure |
|----------|----------|----------|-----------------|---------------|---------------------|
| Entry    | 100      | 100      | 10              | 10            | 20 lots             |
| +5min    | 120      | 80       | 3               | 13            | 23 lots             |
| +10min   | 140      | 60       | 2               | 15            | 25 lots             |
| +15min   | 160      | 40       | 5               | 20            | 30 lots             |
| +20min   | 180      | 25       | 8               | 28            | 38 lots             |
| +25min   | 200      | 15       | 14              | 42            | 52 lots             |

After 25 minutes of steady trending, you've gone from 20 lots to 52 lots, and **if the market reverses**, those 42 PE lots get destroyed.

### Risk B: Margin Exhaustion

Each short option requires margin. The algo can sell itself into a corner where there's no margin left for the next adjustment.

### Risk C: 0DTE Gamma Risk

Near expiry, ATM options have extreme gamma. A small move in underlying can cause 50-100%+ premium changes. This makes 5-minute intervals potentially too slow.

### Risk D: Whipsaw Destruction

In a choppy market that oscillates every 5-10 minutes, the algo consistently sells at low premiums (after the opposite side decayed) to cover losses, then the market reverses and those new positions immediately go underwater. You accumulate lots on BOTH sides simultaneously.

---

## 3. REFINED ALGORITHM — COMPLETE SPECIFICATION

### 3.1 Data Structures

```
MoneyPowerState:
  # Initial positions
  ce_strike: float                      # CE strike price (X)
  pe_strike: float                      # PE strike price (Y)
  initial_ce_lots: int                  # Initial CE lots sold
  initial_pe_lots: int                  # Initial PE lots sold
  initial_ce_premium: float             # CE entry premium per lot
  initial_pe_premium: float             # PE entry premium per lot
  
  # Position tracking (list of all fills)
  ce_positions: List[Fill]              # [{lots, premium, timestamp, is_adjustment}]
  pe_positions: List[Fill]              # [{lots, premium, timestamp, is_adjustment}]
  
  # Derived state (recomputed after each adjustment)
  total_ce_lots: int                    # Sum of all CE lots (original + adjustments)
  total_pe_lots: int                    # Sum of all PE lots (original + adjustments)
  ce_adjustment_lots: int               # Only the adjustment CE lots (excludes original)
  pe_adjustment_lots: int               # Only the adjustment PE lots (excludes original)
  ce_adjustment_avg: float              # Weighted avg premium of CE adjustment fills
  pe_adjustment_avg: float              # Weighted avg premium of PE adjustment fills
  
  # Trigger levels (updated after each adjustment)
  ce_trigger_price: float               # CE price must exceed this to trigger adjustment
  pe_trigger_price: float               # PE price must exceed this to trigger adjustment
  last_ce_trigger_price: float          # Previous CE trigger (for incremental loss calc)
  last_pe_trigger_price: float          # Previous PE trigger (for incremental loss calc)
  
  # Direction tracking
  last_adjustment_side: str             # 'CE' or 'PE' — which side was the aggressor last
  consecutive_same_side: int            # How many consecutive adjustments on same side
  
  # P&L tracking
  total_premium_collected: float        # Sum of ALL premiums collected (all positions)
  total_ce_premium: float               # Total premium from CE side
  total_pe_premium: float               # Total premium from PE side
  realized_pnl: float                   # If any positions are closed
  
  # Safety
  total_lots_cap_reached: bool          # True if position limit hit
  margin_warning: bool                  # True if margin is getting tight
```

```
Fill:
  lots: int
  premium: float                        # Per-lot premium at fill time
  timestamp: datetime
  is_adjustment: bool                   # True if this was an adjustment, False if initial
  covering_loss: float                  # The loss amount this fill was meant to cover
```

### 3.2 Configuration Parameters

```yaml
money_power:
  # === ENTRY PARAMETERS ===
  underlying: "NIFTY"                   # or BANKNIFTY, FINNIFTY, etc.
  expiry: "0DTE"                        # or specific date: "2026-02-20"
  ce_strike: 24000                      # CE strike to sell
  pe_strike: 23800                      # PE strike to sell
  initial_lots: 10                      # Lots per side at entry
  lot_size: 25                          # Contract lot size (NIFTY=25, BANKNIFTY=15)
  
  # === TIMING ===
  adjustment_interval_seconds: 300      # 5 minutes default
  min_adjustment_interval_seconds: 60   # Minimum allowed (prevents over-trading)
  hot_reload_enabled: true              # Allow changing interval via WebUI
  instant_trigger_enabled: true         # Allow manual instant adjustment trigger
  
  # === ADJUSTMENT LOGIC ===
  rounding_mode: "ceil"                 # "ceil" (always round up), "round" (nearest), "floor" (round down)
  min_adjustment_lots: 1                # Minimum lots per adjustment (never sell 0)
  max_adjustment_lots: 20              # Maximum lots per single adjustment
  premium_buffer_pct: 5.0              # Sell 5% MORE lots than needed (safety buffer)
  
  # === SAFETY LIMITS (CRITICAL) ===
  max_total_lots_per_side: 100          # Absolute cap on CE or PE lots
  max_total_lots_combined: 150          # Absolute cap on CE + PE combined lots
  max_adjustments_count: 30             # Max number of adjustment events before forced stop
  max_loss_amount: 50000                # Hard stop-loss in currency (absolute max loss)
  max_margin_usage_pct: 80.0            # Stop adjusting if margin usage > 80%
  min_premium_to_sell: 5.0              # Don't sell options worth less than 5 (illiquid/pointless)
  
  # === WHIPSAW PROTECTION ===
  consecutive_same_side_limit: 5        # After 5 consecutive adjustments on same side, pause
  oscillation_cooldown_seconds: 600     # After direction change, wait 10 min before re-adjusting
  min_trigger_move_pct: 10.0            # Require at least 10% price move to trigger (avoids micro-adjustments)
  
  # === EXPIRY BEHAVIOR ===
  stop_adjustments_before_expiry_mins: 15    # Stop making new adjustments 15 min before expiry
  auto_close_before_expiry_mins: 5           # Auto-close ALL positions 5 min before expiry
  let_expire_worthless: false                # If true, let OTM options expire instead of closing
  
  # === MONITORING & ALERTS ===
  websocket_updates: true               # Push real-time state to WebUI
  alert_on_adjustment: true             # Notify user on each adjustment
  alert_on_direction_change: true       # Notify when market direction reverses
  alert_on_safety_trigger: true         # Notify when any safety limit is hit
  log_level: "INFO"                     # DEBUG for detailed tracking
```

### 3.3 Core Algorithm — Step by Step

#### PHASE 0: INITIALIZATION

```
1. Validate all config parameters
2. Fetch current CE and PE option prices from broker API
3. Place initial sell orders:
   - Sell {initial_lots} of CE at market/limit price → record fill
   - Sell {initial_lots} of PE at market/limit price → record fill
4. Set initial state:
   - ce_trigger_price = initial_ce_premium  (entry price)
   - pe_trigger_price = initial_pe_premium  (entry price)
   - last_ce_trigger_price = initial_ce_premium
   - last_pe_trigger_price = initial_pe_premium
5. Start the adjustment loop timer
6. Push state to WebUI via WebSocket
```

#### PHASE 1: MONITORING LOOP (runs every `adjustment_interval_seconds`)

```
EVERY INTERVAL:
  1. Fetch current CE price (ce_current) and PE price (pe_current)
  2. Check safety limits → if any breached, STOP (Phase 4)
  3. Check expiry proximity → if within stop_adjustments window, SKIP
  4. Determine if adjustment is needed:
  
     ce_needs_adjustment = ce_current > ce_trigger_price
     pe_needs_adjustment = pe_current > pe_trigger_price
     
  5. If NEITHER needs adjustment → log "no action", continue to next interval
  6. If BOTH need adjustment → handle the LARGER loss side first (see Phase 2B)
  7. If ONE needs adjustment → proceed to Phase 2A
```

#### PHASE 2A: SINGLE-SIDE ADJUSTMENT

**Case: CE is above trigger (market moved up, CE losing money)**

```
1. Calculate incremental loss on CE side:
   
   IF this is the first adjustment on CE side:
     ce_incremental_loss = (ce_current - ce_trigger_price) × total_ce_lots
   ELSE:
     ce_incremental_loss = (ce_current - last_ce_trigger_price) × total_ce_lots
   
   Note: total_ce_lots includes ALL CE lots (original + any prior CE adjustments)

2. Get current PE price (pe_current) — this is the hedge instrument
   
3. Check if PE price is too low to sell:
   IF pe_current < min_premium_to_sell:
     → LOG WARNING "PE premium too low to hedge, skipping adjustment"
     → ALERT user
     → CONTINUE (do NOT sell worthless options)
   
4. Calculate lots needed:
   raw_lots = ce_incremental_loss / pe_current
   
   Apply buffer:
   buffered_lots = raw_lots × (1 + premium_buffer_pct / 100)
   
   Apply rounding:
   adjustment_lots = ceil(buffered_lots)  # or round/floor per config
   
   Apply limits:
   adjustment_lots = max(min_adjustment_lots, adjustment_lots)
   adjustment_lots = min(max_adjustment_lots, adjustment_lots)
   
   Check position cap:
   IF (total_pe_lots + adjustment_lots) > max_total_lots_per_side:
     adjustment_lots = max_total_lots_per_side - total_pe_lots
     IF adjustment_lots <= 0:
       → LOG "PE position cap reached, cannot hedge further"
       → ALERT user → STOP or CONTINUE depending on config
   
5. Execute: Sell {adjustment_lots} lots of PE at current market price
   → Record fill in pe_positions
   
6. Update state:
   last_ce_trigger_price = ce_trigger_price
   ce_trigger_price = ce_current          # New CE trigger = current CE price
   pe_trigger_price = pe_current          # New PE trigger = current PE price at time of selling
   Recompute: total_pe_lots, pe_adjustment_lots, pe_adjustment_avg
   Update: total_premium_collected
   last_adjustment_side = 'CE'            # CE was the aggressor
   
7. Push updated state to WebUI
```

**Case: PE is above trigger (market moved down, PE losing money)**
> Mirror of above — swap CE↔PE in all calculations.

#### PHASE 2B: BOTH SIDES ABOVE TRIGGER (Rare but Possible)

This can happen when:
- Volatility spikes (both options get more expensive)
- Strikes are close to ATM and underlying whipsaws within the interval
- After a gap move that crosses both triggers

```
1. Calculate ce_loss = (ce_current - ce_trigger_price) × total_ce_lots
2. Calculate pe_loss = (pe_current - pe_trigger_price) × total_pe_lots
3. net_loss = ce_loss - pe_loss

   IF net_loss > 0:   # CE side is losing MORE
     → Hedge CE loss by selling PE (but PE is ALSO above trigger!)
     → In this case, use net_loss as the amount to hedge
     → adjustment_lots = ceil(net_loss / pe_current)
     → Sell PE lots to cover net difference
     
   IF net_loss < 0:   # PE side is losing MORE
     → Mirror: hedge PE loss by selling CE
     → adjustment_lots = ceil(abs(net_loss) / ce_current)
     
   IF net_loss ≈ 0:   # Both roughly equal
     → No adjustment needed (losses offset each other)
     → Update BOTH trigger prices to current prices

4. Update all trigger prices to current values
```

#### PHASE 2C: REVERSAL HANDLING (Direction Change)

When the market changes direction, the positions accumulated to hedge one side now become the risk themselves.

**Detection:**
```
direction_changed = (last_adjustment_side == 'CE' and pe_needs_adjustment) or
                    (last_adjustment_side == 'PE' and ce_needs_adjustment)
```

**Reversal Logic:**

When market was going UP (CE was aggressor, we accumulated extra PE shorts), now market goes DOWN:

```
1. The extra PE positions (adjustment fills) are now losing money.
   PE adjustment positions: [{lots_1, premium_1}, {lots_2, premium_2}, ...]
   
   pe_adjustment_avg = Σ(lots_i × premium_i) / Σ(lots_i)  # weighted average
   
2. Calculate total PE loss:
   
   a) Original PE loss (if pe_current > initial_pe_premium):
      original_pe_loss = (pe_current - initial_pe_premium) × initial_pe_lots
      But only if pe_current > initial_pe_premium (otherwise original PE is fine)
   
   b) Adjustment PE loss:
      adjustment_pe_loss = (pe_current - pe_adjustment_avg) × pe_adjustment_lots
      But only if pe_current > pe_adjustment_avg (otherwise adjustments are fine)
   
   c) Total incremental PE loss to hedge:
      = original_pe_loss + adjustment_pe_loss
      But SUBTRACT any premium already collected from prior CE adjustments
      (prior CE adjustments were sold to cover earlier PE losses)

3. Hedge by selling CE:
   adjustment_lots = ceil(total_pe_loss / ce_current)
   [apply all limits from Phase 2A]
   
4. Update triggers and state
```

**Simplified Reversal Rule:**

On the FIRST tick of a reversal, the incremental loss is calculated from the trigger prices (which were set at the last adjustment). On subsequent ticks in the same direction, it's always the delta from the last trigger.

This means the reversal handling is actually just **the normal Phase 2A logic** — the only special thing is:
- Reset `consecutive_same_side` counter
- Apply `oscillation_cooldown_seconds` if configured
- Alert the user that direction changed

### 3.4 Trigger Price Update Rules (CRITICAL)

This is the most important part to get right. After every adjustment:

```
When CE was the aggressor (CE rose, we sold more PE):
  ce_trigger_price = ce_current    # CE must exceed THIS to trigger again
  pe_trigger_price = pe_current    # New PE floor (the price at which we sold PE)

When PE was the aggressor (PE rose, we sold more CE):
  pe_trigger_price = pe_current    # PE must exceed THIS to trigger again  
  ce_trigger_price = ce_current    # New CE floor (the price at which we sold CE)
```

**Why both triggers update:** Because we want the algo to be quiet unless there's a NEW incremental loss beyond what we've already hedged. Setting both triggers to current prices means:
- No action if both sides stay at or below current levels
- Action only on NEW moves beyond the already-hedged zone

### 3.5 The Incremental Loss Formula (UNIFIED)

Rather than tracking "is this the first adjustment" vs "subsequent adjustment", use ONE formula:

```
incremental_loss_on_side_X = (current_price_X - trigger_price_X) × total_lots_X

IF incremental_loss_on_side_X > 0:
  → Hedge by selling lots on side Y
  → lots_to_sell = ceil(incremental_loss_on_side_X / current_price_Y)
  → Update both triggers to current prices
  
IF incremental_loss_on_side_X <= 0:
  → No action needed for side X
```

This ONE formula handles:
- First adjustment (trigger_price = entry_price, so it's entry-to-current)
- Subsequent same-direction adjustments (trigger_price = last adjusted level)
- Reversals (trigger_price for the other side was set when we sold adjustments)
- Both sides (just check both, handle larger loss first)

---

## 4. SAFETY MECHANISMS

### 4.1 Position Size Circuit Breaker

```python
def check_position_limits(state, config):
    violations = []
    
    if state.total_ce_lots >= config.max_total_lots_per_side:
        violations.append(f"CE lots at cap: {state.total_ce_lots}")
    
    if state.total_pe_lots >= config.max_total_lots_per_side:
        violations.append(f"PE lots at cap: {state.total_pe_lots}")
    
    combined = state.total_ce_lots + state.total_pe_lots
    if combined >= config.max_total_lots_combined:
        violations.append(f"Combined lots at cap: {combined}")
    
    if state.adjustment_count >= config.max_adjustments_count:
        violations.append(f"Max adjustments reached: {state.adjustment_count}")
    
    return violations
```

### 4.2 Max Loss Hard Stop

```python
def check_max_loss(state, config, ce_current, pe_current):
    # Mark-to-market P&L
    ce_mtm = sum(fill.lots * (fill.premium - ce_current) for fill in state.ce_positions)
    pe_mtm = sum(fill.lots * (fill.premium - pe_current) for fill in state.pe_positions)
    
    unrealized_pnl = ce_mtm + pe_mtm
    
    if unrealized_pnl < -config.max_loss_amount:
        return True, f"Max loss breached. Unrealized: {unrealized_pnl}"
    return False, ""
```

### 4.3 Minimum Premium Guard

Never sell options trading below `min_premium_to_sell`. This prevents:
- Selling near-zero premium options that provide negligible hedge
- Accumulating massive lot counts for tiny premium
- Liquidity issues with deep OTM options near expiry

### 4.4 Whipsaw Detector

```python
def check_whipsaw(state, config):
    """Detect oscillating market"""
    if state.adjustment_count < 4:
        return False
    
    # Look at last 4 adjustments — did we alternate sides?
    last_4 = state.adjustment_history[-4:]
    sides = [a.side for a in last_4]
    
    # Pattern like CE, PE, CE, PE = whipsaw
    alternating = all(sides[i] != sides[i+1] for i in range(len(sides)-1))
    
    if alternating:
        return True  # Pause adjustments, alert user
    return False
```

### 4.5 Margin Check (Pre-Adjustment)

Before placing any adjustment order:
```python
def check_margin(api_client, new_lots, option_price, config):
    available_margin = api_client.get_available_margin()
    estimated_margin_needed = estimate_margin_for_short(new_lots, option_price)
    
    margin_after = available_margin - estimated_margin_needed
    margin_usage_pct = (1 - margin_after / total_margin) * 100
    
    if margin_usage_pct > config.max_margin_usage_pct:
        return False, f"Margin usage would be {margin_usage_pct}%"
    return True, ""
```

---

## 5. COMPLETE FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                    MONEY POWER — MASTER FLOW                     │
└─────────────────────────────────────────────────────────────────┘

USER INPUT (WebUI)
    │
    ▼
┌─────────────────┐
│  VALIDATE CONFIG │──── Invalid? ──→ Show error in WebUI
│  (strikes, lots, │
│   limits, expiry) │
└────────┬────────┘
         │ Valid
         ▼
┌─────────────────┐
│  PLACE INITIAL   │
│  ORDERS          │──── Failed? ──→ Retry / Alert user
│  Sell CE + PE    │
└────────┬────────┘
         │ Filled
         ▼
┌─────────────────────────────────────────────────────────┐
│                  MONITORING LOOP                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Every {interval} seconds:                        │    │
│  │                                                   │    │
│  │  1. Fetch CE_price, PE_price                     │    │
│  │  2. ─── SAFETY CHECKS ───                       │    │
│  │     ├─ Max loss breached?      → EMERGENCY STOP  │    │
│  │     ├─ Position cap reached?   → PAUSE + ALERT   │    │
│  │     ├─ Max adjustments?        → STOP ADJUSTING   │    │
│  │     ├─ Near expiry?            → AUTO CLOSE       │    │
│  │     ├─ Margin insufficient?    → PAUSE + ALERT   │    │
│  │     ├─ Whipsaw detected?       → COOLDOWN        │    │
│  │     └─ Premium too low?        → SKIP ADJUSTMENT  │    │
│  │                                                   │    │
│  │  3. ─── ADJUSTMENT CHECK ───                     │    │
│  │     ce_loss = (CE_price - ce_trigger) × CE_lots  │    │
│  │     pe_loss = (PE_price - pe_trigger) × PE_lots  │    │
│  │                                                   │    │
│  │     IF ce_loss > 0 AND pe_loss > 0:              │    │
│  │       → Handle NET difference (Phase 2B)          │    │
│  │     ELIF ce_loss > 0:                             │    │
│  │       → Sell more PE to cover (Phase 2A)          │    │
│  │     ELIF pe_loss > 0:                             │    │
│  │       → Sell more CE to cover (Phase 2A)          │    │
│  │     ELSE:                                         │    │
│  │       → No action needed                          │    │
│  │                                                   │    │
│  │  4. ─── POST-ADJUSTMENT ───                      │    │
│  │     Update triggers to current prices             │    │
│  │     Record fill details                           │    │
│  │     Push state to WebUI                           │    │
│  │     Send notification                             │    │
│  │                                                   │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│                     ▼                                    │
│              Wait {interval}                             │
│                     │                                    │
│                     └──────── Loop ──────────────────────│
│                                                          │
│  ─── EXIT CONDITIONS ───                                 │
│  • User clicks STOP in WebUI                             │
│  • Expiry reached → auto-close window                    │
│  • Max loss breached                                     │
│  • Position cap reached with no more room                │
│  • Manual instant trigger via WebUI                      │
└─────────────────────────────────────────────────────────┘
```

---

## 6. SCENARIOS — VERIFIED WITH CORRECT MATH

### Scenario 1: Market Goes UP Steadily

| Time | CE Price | PE Price | Action | New PE Sold | Total CE | Total PE |
|------|----------|----------|--------|-------------|----------|----------|
| T0   | 100      | 100      | Entry  | 10          | 10       | 10       |
| T+5  | 120      | 80       | Hedge  | ceil(200/80)=3 | 10   | 13       |
| T+10 | 130      | 70       | Hedge  | ceil(100/70)=2 | 10   | 15       |
| T+15 | 140      | 60       | Hedge  | ceil(100/60)=2 | 10   | 17       |

**Key check at T+10:** 
- `ce_trigger=120`, CE is at 130
- incremental loss = (130-120)×10 = 100
- lots needed = ceil(100/70) = 2 ✓
- Update: ce_trigger=130, pe_trigger=70

### Scenario 2: Market Reverses After Going UP

After Scenario 1, positions: CE:10@100, PE:10@100+3@80+2@70+2@60

- pe_adjustment_avg = (80×3+70×2+60×2)/7 = 71.43
- pe_trigger was set to 60 (from last adjustment)

| Time | CE Price | PE Price | Action | Calculation |
|------|----------|----------|--------|-------------|
| T+20 | 130 | 70 | None | PE(70) ≤ pe_trigger(70)? Actually pe_trigger=60, so PE 70>60 → YES trigger! |

Wait — this is important. After T+15 where we sold PE at 60, the triggers were:
- ce_trigger = 140 (CE was at 140)
- pe_trigger = 60 (PE was at 60 when we sold)

So if PE rises to 70 at T+20: 70 > 60 ✓ → trigger.

pe_loss = (70 - 60) × 17 = 170 (ALL 17 PE lots are losing from 60 to 70)

Hedge: sell CE lots = ceil(170 / 130) = ceil(1.31) = 2

This is **correct** behavior. The trigger fires because ANY move above the last-adjusted level on PE side means new unhedged losses.

### Scenario 3: Oscillating Market (UP→DOWN→UP)

| Step | CE | PE | Action | New Lots | Cum CE | Cum PE | Note |
|------|----|----|--------|----------|--------|--------|------|
| Entry| 100| 100| Sell both | 10+10 | 10 | 10 | Triggers: CE=100, PE=100 |
| +5   | 115| 85 | Sell 2 PE | 2 | 10 | 12 | Loss=(115-100)×10=150, 150/85=1.76→2 |
| +10  | 105| 95 | Sell 2 CE | 2 | 12 | 12 | PE 95>85 trigger. Loss=(95-85)×12=120, 120/105=1.14→2 |
| +15  | 115| 85 | Sell 2 PE | 2 | 12 | 14 | CE 115>105 trigger. Loss=(115-105)×12=120, 120/85=1.41→2 |
| +20  | 105| 95 | Sell 2 CE | 2 | 14 | 14 | PE 95>85 trigger. Loss=(95-85)×14=140, 140/105=1.33→2 |

**After 20 minutes of oscillation:** 14 CE lots + 14 PE lots = 28 lots (from 20). AND all the premium collected from adjustments is at relatively low prices. This is the **whipsaw trap**. 

**The whipsaw detector would fire after step +15** (3+ alternating direction adjustments) and pause the algo.

### Scenario 4: Gradual Theta Decay (Best Case)

If both CE and PE decay steadily from 100 toward 0:

| Time | CE | PE | Action | Note |
|------|-----|----|--------|------|
| T0   | 100 | 100| Entry  | Triggers: CE=100, PE=100 |
| T+5  | 95  | 95 | None   | Both below triggers |
| T+10 | 88  | 88 | None   | Both below triggers |
| T+15 | 75  | 75 | None   | Both below triggers |
| T+30 | 50  | 50 | None   | Both below triggers |
| T+60 | 20  | 20 | None   | Both below triggers |
| Expiry| 0  | 0  | Expire | Full premium captured: 2000 |

**Zero adjustments needed.** Pure profit from theta decay.

---

## 7. ARCHITECTURE — INTEGRATION WITH EXISTING CODEBASE

The Money Power algorithm fits into the existing strategy framework:

```
webui/backend/options_strategy/
├── strategies/
│   ├── base_strategy.py              # Existing — MoneyPowerStrategy extends this
│   ├── mv_straddle_strategy.py       # Existing reference implementation
│   └── money_power_strategy.py       # NEW — Core algorithm logic
├── money_power/                       # NEW — Algorithm-specific modules
│   ├── __init__.py
│   ├── state_manager.py              # Position tracking, state persistence
│   ├── adjustment_engine.py          # Core adjustment calculation logic
│   ├── safety_checks.py             # All circuit breakers and limits
│   ├── trigger_tracker.py           # Trigger price management
│   └── whipsaw_detector.py          # Oscillation detection
├── strategy_models.py               # Extend with MoneyPower-specific models
├── strategy_manager.py              # Register MoneyPowerStrategy
├── strategy_monitor.py              # Add MoneyPower monitoring hooks
├── strategy_risk.py                 # Add MoneyPower risk checks
└── strategy_routes.py               # Add API endpoints for MoneyPower
```

### WebUI Integration

```
webui/frontend/
├── pages/
│   └── money_power.html              # NEW — Dedicated dashboard
├── js/
│   └── money_power.js                # NEW — Real-time state display
```

**WebUI Dashboard will show:**
- Live CE/PE prices vs trigger levels (chart)
- Current positions table with P&L
- Adjustment history log
- Total lots gauge (with cap indicator)
- Margin usage bar
- Start/Stop/Instant-Trigger buttons
- Config editor with hot-reload
- Whipsaw warning indicator

---

## 8. IMPLEMENTATION SEQUENCE

### Phase 1: Core Engine (No broker integration)
1. `MoneyPowerState` dataclass — position/trigger tracking
2. `AdjustmentEngine` — pure calculation logic (testable without API)
3. `SafetyChecks` — all circuit breakers
4. Unit tests with all 4 scenarios above

### Phase 2: Strategy Integration
5. `MoneyPowerStrategy(BaseStrategy)` — implements `calculate_legs`, `validate_parameters`, etc.
6. Register in `StrategyManager`
7. Add to `StrategyType` enum
8. Add risk checks in `strategy_risk.py`

### Phase 3: Monitoring Loop
9. Async monitoring loop in `StrategyMonitor` with configurable interval
10. Hot-reload support for interval changes
11. Instant-trigger via WebSocket command
12. State persistence to SQLite (resume after restart)

### Phase 4: WebUI
13. Dashboard page with live state
14. Config editor
15. Manual controls (start/stop/trigger/close-all)
16. Adjustment history table
17. Position chart

### Phase 5: Paper Trading & Validation
18. Paper trade mode (simulated orders)
19. Run through all 4 scenarios with real market data
20. Validate math against manual calculations
21. Stress test: what happens with 1-second intervals?

---

## 9. WHAT MAKES THIS "BEST OF BEST"

| Feature | Why It Matters |
|---------|---------------|
| **Unified incremental loss formula** | One formula handles all cases — no special-casing for first/subsequent/reversal |
| **Dual trigger tracking** | Both CE and PE triggers update after every adjustment — prevents false triggers |
| **Position cap** | Prevents exponential lot growth from destroying the account |
| **Min premium guard** | Won't sell worthless options just to "hedge" |
| **Whipsaw detector** | Catches oscillating markets before they accumulate massive bilateral exposure |
| **Margin pre-check** | Never places an order that would blow the margin |
| **Max loss hard stop** | Absolute floor — the strategy WILL stop if losses exceed threshold |
| **Oscillation cooldown** | After a direction change, waits before re-adjusting (lets the dust settle) |
| **Hot reload** | Change interval or trigger instantly from WebUI without restarting |
| **State persistence** | Survives bot restart — resumes from exactly where it left off |
| **Premium buffer** | Sells slightly more than needed (5%) to ensure coverage even with slippage |
| **Both-sides-triggered handling** | Handles the rare case where both CE and PE exceed triggers simultaneously |

---

## 10. OPEN QUESTIONS FOR USER

Before implementation begins:

1. **What broker API?** — The lot rounding and order types depend on this (Deribit, Binance, etc.)
2. **Which underlying?** — NIFTY/BANKNIFTY (Indian markets) or BTC/ETH (crypto)?
3. **Lot size?** — NIFTY=25, BANKNIFTY=15, or crypto where qty=contracts?
4. **Order type for adjustments?** — Market orders (guaranteed fill, slippage) or limit orders (no slippage, may not fill)?
5. **Should the algo also BUY options as a hard hedge?** — e.g., buy far OTM puts/calls as catastrophic protection?
6. **Maximum capital allocated?** — helps set `max_loss_amount` and `max_total_lots`
7. **Trading hours constraint?** — Should the algo only run during market hours? Auto-stop after hours?

---

*This plan is ready for implementation. Let me know which phase to start with.*
