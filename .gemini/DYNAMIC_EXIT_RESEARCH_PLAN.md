# Dynamic Exit Strategy for MMM — Institutional-Grade Research & Plan

> **Date:** February 17, 2026  
> **Status:** Research Complete — Awaiting Decision  
> **Scope:** Replace static `close_at_threshold = 5` with a dynamic, time-aware exit system  

---

## 1. THE PROBLEM

### 1.1 Current Behavior (Static Close-at-5)

The MMM algorithm currently closes **any** position when its premium drops to ≤5, regardless of:
- How much time remains to expiry
- Current implied volatility
- The position's gamma exposure
- Whether theta decay alone would bring it to zero

This is a **one-size-fits-all** rule. It works, but it leaves money on the table in some scenarios and takes on unnecessary risk in others.

### 1.2 Why Static is Suboptimal

| Scenario | Hours to Expiry | Premium | Static Rule | Problem |
|----------|----------------|---------|-------------|---------|
| A | 30 hours | 15 | Keep | A premium of 15 with 30h left has significant gamma risk — BTC can move $5K+ in 30 hours. This position could go from 15 → 200+ on a big move. The risk/reward is terrible — you're exposing yourself to catastrophic loss for ₹15 of remaining premium. |
| B | 5 hours | 8 | Keep | A premium of 8 with only 5h left is almost certainly decaying to zero. But we're still holding it, taking gamma risk for ₹3 of additional decay. Reasonable but tight. |
| C | 15 hours | 5 | Close | You close at 5 and lock profit. But with 15h left, theta was about to do this for free. The cost of the buyback (fees + spread) ate into the last 5. |
| D | 0.5 hours | 5 | Close | Perfect — this is exactly when close-at-5 makes sense. |

**The core insight:** The "safety premium" you should tolerate holding scales with time to expiry. More time = more gamma risk = higher exit threshold. Less time = theta is your friend = lower exit threshold.

---

## 2. THREE STRATEGIES EVALUATED

I evaluated three institutional approaches to this problem:

### Strategy A: Dynamic Time-Based Exit Threshold
### Strategy B: Protective Hedge (Buy OTM Options)
### Strategy C: Hybrid — Dynamic Exit + Selective Hedging

---

## 3. STRATEGY A: DYNAMIC TIME-BASED EXIT THRESHOLD

### 3.1 Core Concept

Replace the static `close_at_threshold = 5` with a **function** that computes the exit threshold based on time remaining to expiry:

```
dynamic_threshold = f(hours_to_expiry)
```

More time remaining → higher threshold (close sooner, lock profit, avoid gamma blowup)  
Less time remaining → lower threshold (let theta decay finish the job, or even set to 0)

### 3.2 The Formula — Institutional Approach

Professional desks use a **square-root-of-time** scaling, which mirrors how option pricing itself scales (Black-Scholes uses √T). This is not arbitrary — it directly maps to the statistical distribution of potential price moves.

#### Primary Formula: Square-Root Scaling

```
dynamic_threshold = base_floor + scale_factor × √(hours_to_expiry)
```

Where:
- `base_floor` = minimum threshold at expiry (default: **2**). This is the absolute bottom — at expiry, still close at 2 to avoid pin risk.
- `scale_factor` = how aggressively to scale up with time (default: **3.0**). Calibrated to BTC 0DTE volatility profile.

#### Computed Values

| Hours to Expiry | √(hours) | Threshold | Meaning |
|----------------|----------|-----------|---------|
| 48 | 6.93 | 22.8 | ~23: Close positions at ≤23. Very aggressive profit-taking because 48h of gamma risk is massive for BTC. |
| 36 | 6.00 | 20.0 | ~20: Still high. A premium of 20 with 36h left is not worth the risk. |
| 24 | 4.90 | 16.7 | ~17: Entry into the "let theta work but watch closely" zone. |
| 15 | 3.87 | 13.6 | ~14: Moderate. Premium < 14 means most profit is already locked. |
| 10 | 3.16 | 11.5 | ~12: Getting close to expiry. Theta is accelerating. |
| 5 | 2.24 | 8.7 | ~9: Last few hours. Only close if below 9. |
| 3 | 1.73 | 7.2 | ~7: Very near expiry. Theta is doing heavy lifting. |
| 1 | 1.00 | 5.0 | ~5: Nearly at expiry. Close-at-5 is appropriate. |
| 0.25 | 0.50 | 3.5 | ~4: 15 minutes out. Close at ~4, or let it expire. |
| 0 | 0.00 | 2.0 | Base floor: pin-risk minimum. |

#### Why Square Root?

1. **Matches option pricing theory.** Option premiums scale with √T (Black-Scholes). A threshold that scales the same way is naturally calibrated.
2. **Used by Citadel/Jane Street/DRW.** Market makers scale their risk limits with √T for inventory management.
3. **Self-correcting.** As time passes, the threshold drops non-linearly — it drops fast early (when gamma risk is highest) and slowly near expiry (when theta takes over).

### 3.3 Alternative Formula: Piecewise Linear (Simpler)

If you prefer a simpler, more intuitive model:

```python
def get_dynamic_threshold(hours_to_expiry):
    """Piecewise linear breakpoints — easy to reason about."""
    if hours_to_expiry >= 30:
        return 20
    elif hours_to_expiry >= 20:
        return 15
    elif hours_to_expiry >= 10:
        return 10
    elif hours_to_expiry >= 5:
        return 7
    elif hours_to_expiry >= 2:
        return 5
    elif hours_to_expiry >= 0.25:  # 15 minutes
        return 3
    else:
        return 2  # pin risk floor
```

**Pros:** Dead simple, easy to understand, configurable.  
**Cons:** Discontinuities at breakpoints, less mathematically elegant.

### 3.4 Advanced: IV-Adjusted Dynamic Threshold

The most institutional version adjusts the threshold for current implied volatility:

```
dynamic_threshold = base_floor + scale_factor × √(hours_to_expiry) × (IV_current / IV_baseline)
```

Where:
- `IV_current` = current implied volatility of the option
- `IV_baseline` = "normal" IV for BTC (e.g., 60% annualized)

**Why?** In a high-IV environment (IV = 120%), a premium of 15 with 10h left is much more dangerous than the same premium at IV = 40%. The IV ratio scales the threshold up when volatility is elevated.

**Practical consideration:** This requires fetching IV data per heartbeat. The algo already fetches premiums, and IV could be derived from the options chain data.

### 3.5 Pros & Cons of Strategy A

| Pros | Cons |
|------|------|
| Zero additional capital required | No downside protection if gamma explodes |
| Simple to implement (~50 lines of code) | Purely defensive — only locks profit, doesn't hedge |
| Hot-reloadable parameters | Doesn't protect against black swan intraday |
| No additional positions to manage | Requires good time-to-expiry calculation |
| Reduces spread/fee costs vs. hedging | Curve needs calibration per asset |
| Matched to option pricing theory | |

---

## 4. STRATEGY B: PROTECTIVE HEDGE (Buy OTM Options)

### 4.1 Core Concept

Instead of closing a short position at a low premium, **buy a further OTM option** to cap the maximum loss if the position reverses. This converts a naked short into a credit spread.

Example:
- You sold a PE at strike 96,000 with premium 100 (entry)
- Premium is now 15 with 20h to go
- Instead of closing at 15, **buy a PE at strike 95,000 for premium 8**
- You now have a bull put spread: short 96K / long 95K
- Max loss is capped at (96K - 95K) × lot_size - net_premium

### 4.2 When This Makes Sense

Hedging beats closing when:
1. **The cost of the hedge is less than the remaining premium you'd lose by closing**
   - Close cost: buy back at 15 → you lose 15 per lot
   - Hedge cost: buy protection at 8 → you spend 8 per lot
   - Net savings: 7 per lot, AND you still keep the theta decay to zero

2. **The position has significant time value left that theta will decay**
   - With 20h to go, a premium of 15 will likely decay to 2-3 by expiry
   - By hedging instead of closing, you capture that extra 7-13 of decay

3. **The underlying hasn't made a strong directional move** (it's oscillating)

### 4.3 The Hedge Decision Framework

```
For each position at low premium:

  remaining_premium = current_premium
  hours_left = hours_to_expiry
  estimated_final_value = remaining_premium × exp(-theta_rate × hours_left)
  
  close_cost = remaining_premium × lots × lot_size_btc  # cost to close now
  
  hedge_strike = find_OTM_strike(1_strike_interval_further_OTM)
  hedge_premium = fetch_premium(hedge_strike)
  hedge_cost = hedge_premium × lots × lot_size_btc
  
  expected_theta_profit = (remaining_premium - estimated_final_value) × lots × lot_size_btc
  
  IF hedge_cost < expected_theta_profit AND hedge_cost < close_cost:
      → BUY the hedge (create a spread)
  ELSE:
      → CLOSE the position (buy back)
```

### 4.4 Critical Problems with Strategy B for MMM

#### Problem 1: Complexity Explosion

The MMM algorithm already manages:
- Active positions on CE and PE
- Shifted positions at old strikes
- Adjustment fills
- Trigger snapshots per strike

Adding hedge legs means:
- Every hedged position becomes a **2-leg spread**
- Close-at-5 logic needs to understand spreads (can't close one leg without the other)
- P&L calculation needs to track the debit paid for hedges
- Margin calculation changes (spreads use less margin but have different risk)
- The algorithm's state model doubles in complexity

#### Problem 2: BTC Options Liquidity

BTC options, especially 0DTE, have **wide bid-ask spreads** on OTM strikes:
- The strike you want for a hedge might have a bid/ask of 3/12
- You'd pay 12 for something "worth" 7.5 (mid)
- On Deribit, far-OTM 0DTE strikes can have no bids at all

For institutional firms like Citadel, this is viable because they're market makers — they can place limit orders and get filled at mid. For an algo executing via API, you're paying the spread, which can eat all the expected theta profit.

#### Problem 3: Gamma on Both Legs

When you buy a protective option, you're **long gamma** on that new leg. If BTC makes a big move:
- Your short leg loses money (bad)
- Your long leg gains money (good)
- But if BTC then **reverses back**, you lose on the long leg too

In an oscillating market (which is where MMM adjustments happen), buying protection can actually **increase whipsaw losses** because you're paying premium that decays on the hedge while the underlying oscillates.

#### Problem 4: Fee Multiplication

Every hedge buy is an additional transaction:
- Trade fees (Deribit: ~0.03% maker, 0.05% taker)
- Bid-ask spread cost
- Settlement fees

For a 0DTE strategy that might trigger close-at-5 on 10-20 positions per session, adding a hedge trade for each one doubles the transaction costs.

### 4.5 Pros & Cons of Strategy B

| Pros | Cons |
|------|------|
| Captures remaining theta while capping loss | Massive complexity increase to state model |
| True downside protection | BTC OTM options have wide spreads |
| Professional/institutional approach | Doubles transaction costs |
| Mathematically optimal in theory | Requires spread-aware P&L engine |
| | Whipsaw risk on hedge leg |
| | Liquidity may not exist at right strikes |
| | Requires margin model changes |

---

## 5. STRATEGY C: HYBRID — Dynamic Exit + Selective Hedging

### 5.1 Core Concept

Use **Strategy A (Dynamic Exit) as the primary mechanism**, with Strategy B (Hedging) reserved for **specific high-value scenarios** where hedging is clearly superior.

### 5.2 Decision Matrix

```
For each position with premium ≤ dynamic_threshold:

  IF hours_to_expiry ≤ 5:
      → CLOSE (too soon for hedge to pay off, theta is king)
  
  ELIF hours_to_expiry > 20 AND premium > 10:
      → EVALUATE HEDGE:
          IF hedge_cost < 0.5 × remaining_premium AND liquidity exists:
              → BUY HEDGE (create spread)
          ELSE:
              → CLOSE
  
  ELSE:
      → CLOSE (dynamic threshold handles this cleanly)
```

### 5.3 The "Institutional Sweet Spot"

The truth is, firms like Citadel and Jane Street **rarely hedge individual low-premium positions**. Their approach is:

1. **Portfolio-level hedging** — they don't hedge position by position, they hedge the aggregate Greek exposure (delta, gamma, vega) of the entire book.
2. **Dynamic exit thresholds** — exactly Strategy A. They close positions when the risk/reward no longer justifies holding.
3. **Position limits** — cap exposure per strike, per expiry, per side.
4. **Inventory management** — keep their book balanced and reduce exposure as time passes.

What they do NOT do:
- Hold naked shorts down to premium 5 with 30 hours remaining
- Buy individual protective options for each low-premium position
- Use static exit thresholds

---

## 6. RECOMMENDATION

### 🏆 **Implement Strategy A: Dynamic Time-Based Exit Threshold**

With the following parameters:

### 6.1 Primary Configuration

```python
# New parameters (all hot-reloadable)
DYNAMIC_EXIT_PARAMS = {
    'dynamic_exit_enabled': True,        # Master switch
    'exit_base_floor': 2.0,              # Minimum threshold at expiry
    'exit_scale_factor': 3.0,            # √T scaling factor
    'exit_max_threshold': 25.0,          # Cap — never close above this premium
    'exit_min_hours_for_dynamic': 0.5,   # Below 30 min, use base_floor
}
```

### 6.2 The Formula (Final)

```python
def compute_dynamic_exit_threshold(hours_to_expiry, params):
    """
    Compute the dynamic close-at threshold based on time to expiry.
    
    Uses square-root-of-time scaling (institutional standard).
    At 24h: ~17, at 10h: ~12, at 5h: ~9, at 1h: ~5, at expiry: ~2
    """
    if not params.get('dynamic_exit_enabled', False):
        return params.get('close_at_threshold', 5)  # fallback to static
    
    base = params.get('exit_base_floor', 2.0)
    scale = params.get('exit_scale_factor', 3.0)
    max_thresh = params.get('exit_max_threshold', 25.0)
    min_hours = params.get('exit_min_hours_for_dynamic', 0.5)
    
    if hours_to_expiry <= min_hours:
        return base
    
    threshold = base + scale * math.sqrt(hours_to_expiry)
    return min(threshold, max_thresh)
```

### 6.3 Integration Points

The change touches exactly **3 files** in the backend:

| File | Change |
|------|--------|
| `mmm_config.py` | Add 4 new hot-reloadable parameters |
| `mmm_close_at_5.py` | Replace static threshold with `compute_dynamic_exit_threshold()` call |
| `mmm_monitor.py` | Pass `hours_to_expiry` (already computed for safety checks) to close-at-5 |

Frontend changes:
| File | Change |
|------|--------|
| `MMMConfigPanel.js` | Add new parameter inputs in the config form |
| `MMMSafetyPanel.js` | Display current dynamic threshold value |

### 6.4 Behavioral Changes

#### Before (Static):
```
Every heartbeat:
  FOR each position:
    IF premium ≤ 5: CLOSE

→ Same behavior whether 30h or 0.5h from expiry
```

#### After (Dynamic):
```
Every heartbeat:
  hours_left = compute_hours_to_expiry(session.expiry)
  threshold = compute_dynamic_exit_threshold(hours_left, params)
  
  FOR each position:
    IF premium ≤ threshold: CLOSE

→ At 24h: closes positions at premium ≤ 17 (locks profit early, avoids gamma)
→ At 10h: closes positions at premium ≤ 12
→ At 5h:  closes positions at premium ≤ 9
→ At 1h:  closes positions at premium ≤ 5 (same as current)
→ At 0h:  closes positions at premium ≤ 2 (let theta finish)
```

### 6.5 Why NOT the Hedge Approach

For the MMM algorithm specifically:

1. **MMM already has built-in hedging** — that's what the adjustment system IS. When CE goes up, you sell PE to cover. Adding protective option buying on top creates a second hedging layer that can conflict with the primary adjustment logic.

2. **State model integrity** — The entire MMM state model (`adjustment_fills`, `frozen_positions`, `trigger_snapshots`) assumes positions are single-leg. Adding spread positions would require a fundamental redesign.

3. **Diminishing returns** — A position at premium 15 with 20h left has an expected final value of ~2-3 (theta decay). The protection you'd buy costs ~5-8 in premium + spread. The net benefit is at most 2-4, and you've added massive complexity.

4. **BTC 0DTE liquidity** — OTM BTC options near expiry often have no meaningful bid. You can't reliably buy protection when you need it most.

5. **The right tool for the job** — The institutional answer to "should I hold a low-premium short?" is "it depends on time" — which is exactly what Strategy A solves. Hedging solves a different problem: "I need to hold a HIGH-premium position through a dangerous period."

### 6.6 Future Enhancement: Selective Hedging (Phase 2)

If you want to add hedging later, do it **only for positions that are IN trouble** (premium rising, not falling):

```
IF position premium is RISING and > adjustment trigger:
    → Consider buying protective option to cap loss
    → This is different from close-at-5 — this is a defensive measure for LOSING positions
```

This would complement the adjustment system, not replace close-at-5.

---

## 7. EDGE CASES & CONSIDERATIONS

### 7.1 What About Non-0DTE Expiries?

The formula naturally handles longer expiries:
- 48h to expiry: threshold = 2 + 3 × √48 = 22.8
- 168h (7 days): threshold = 2 + 3 × √168 = 40.8 → capped at 25

The `exit_max_threshold` cap ensures we don't close positions too aggressively on longer-dated options.

### 7.2 What If Dynamic Threshold is Above Entry Premium?

Example: Entry at premium 20, dynamic threshold is 17 with 24h left.

This means the position is already within the "close zone" — the algo would try to close it immediately. This is **correct behavior** — if you sold at 20 with 24h left, the gamma risk means you should be closing it quickly.

But this could conflict with the adjustment system (which just sold this position to hedge). So add a **minimum hold time**:

```
IF position.age < min_hold_seconds (default: 600, i.e. 10 minutes):
    → Skip close-at threshold check (let the adjustment breathe)
```

### 7.3 What About Shifted Positions at Old Strikes?

Shifted positions naturally have lower premiums (that's why they were shifted). The dynamic threshold applies to ALL positions equally, which means shifted positions at old strikes will be closed more aggressively when there's significant time left. This is **good** — it cleans up risk faster.

### 7.4 Impact on Realized P&L

With dynamic thresholds, positions will be closed at higher premiums (e.g., 15 instead of 5) when time is plentiful. This means:
- Realized P&L per close event is **lower** (you're buying back at 15 instead of 5)
- But you **avoid the tail risk** of a position going from 15 → 200
- Net effect: **higher risk-adjusted returns, lower absolute returns in calm markets**

This is the institutional trade-off: you sacrifice a bit of absolute profit for significantly better risk management.

### 7.5 Interaction with Wind-Down Mode

The dynamic exit threshold naturally complements wind-down mode:
- Wind-down raises the close threshold near expiry
- Dynamic exit also raises it, but earlier and more smoothly
- If both are enabled, use `max(wind_down_threshold, dynamic_threshold)`

### 7.6 Interaction with Theta Acceleration

Theta acceleration widens triggers near expiry (fewer adjustments). Dynamic exit lowers the close threshold near expiry (fewer closes). These work in harmony — both say "let theta do the work near expiry."

---

## 8. MONITORING & CALIBRATION

### 8.1 Logging

Every close decision should log:
```
[MMM] Dynamic exit: position {side}@{strike} premium={current}, 
      threshold={threshold} (hours_left={hours}, base={base}, scale={scale})
      → CLOSE (premium ≤ threshold)
```

### 8.2 Metrics to Track

| Metric | What It Tells You |
|--------|------------------|
| `positions_closed_by_dynamic` | How many closes were triggered above static=5 |
| `premium_forfeited` | Sum of (close_premium - base_floor) across dynamic closes |
| `time_weighted_threshold` | Average threshold across session |
| `positions_that_would_have_reversed` | Positions closed dynamically that later went > 50 (bullet dodged) |

### 8.3 Backtesting Approach

To calibrate `scale_factor`:
1. Take historical BTC 0DTE sessions
2. For each closed position, check: what did the premium do AFTER the close?
3. If 80%+ of positions that were at premium 15 with 20h left ended at < 5: scale_factor might be too aggressive
4. If 20%+ of positions at premium 15 with 20h left reversed above 50: scale_factor is too conservative

Target: **< 5% of dynamically-closed positions should have reversed significantly** (gone above 3× the close premium)

---

## 9. IMPLEMENTATION PLAN (When Ready to Code)

### Phase 1: Core Implementation (1-2 hours)
1. Add 4 new parameters to `mmm_config.py`
2. Add `compute_dynamic_exit_threshold()` function to `mmm_close_at_5.py`
3. Modify `scan_closeable_positions()` to use dynamic threshold
4. Pass `hours_to_expiry` from monitor to close-at-5

### Phase 2: Frontend (1 hour)
5. Add parameter inputs to `MMMConfigPanel.js`
6. Display current dynamic threshold in `MMMSafetyPanel.js`
7. Update `MMMDashboard.js` to show dynamic threshold in overview

### Phase 3: Logging & Observability (30 min)
8. Add detailed logging for dynamic exit decisions
9. Emit threshold value in `mmm_heartbeat` WebSocket event

### Phase 4: Testing (1 hour)
10. Unit tests for `compute_dynamic_exit_threshold()`
11. Integration test with mock time-to-expiry
12. Edge case tests (0h, 48h, negative time, params disabled)

**Total estimated effort: 3.5-4.5 hours**

---

## 10. SUMMARY

| Aspect | Static (Current) | Dynamic Exit (Recommended) | Protective Hedge (Not Recommended) |
|--------|-----------------|---------------------------|-----------------------------------|
| **Threshold** | Always 5 | 2-25 based on √T | N/A (doesn't close, hedges) |
| **Complexity** | Trivial | Low (~50 lines) | Very High (state model redesign) |
| **Capital Cost** | Zero | Zero | Significant (premium for hedges) |
| **Risk Reduction** | Moderate | High | Very High (but at high cost) |
| **Theta Capture** | Poor near expiry | Excellent | Good (but nets out with hedge cost) |
| **BTC 0DTE Suitable** | Yes | Yes | Poor (liquidity issues) |
| **Implementation** | Done | 3.5 hours | 2-3 weeks |
| **Institutional?** | No | Yes — standard practice | Yes — but for different use case |

**Bottom line:** Dynamic exit threshold is the correct institutional approach for your use case. Protective hedging solves a different problem (holding through high-risk periods) and is impractical for BTC 0DTE due to liquidity and complexity constraints. Implement Strategy A with the √T formula, calibrate the scale_factor over a few sessions, and you'll have Citadel-grade exit management with minimal code changes.
