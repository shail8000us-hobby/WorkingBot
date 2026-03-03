# MMM Lot Recycling & Smart Position Management — Implementation Plan

> **Created:** March 3, 2026
> **Status:** PLAN — Ready for Implementation
> **Priority:** HIGH — Current max-lot exhaustion cripples the algo within hours
> **Estimated Effort:** 3-4 implementation sessions

---

## 1. THE PROBLEM — Observed in Production

### 1.1 What We See (mmm06mar26-1 Live Session)

```
Side   Strike   Type           Lots   Entry    Current   P&L
─────────────────────────────────────────────────────────────
CE     73,000   Adj #1          36    94.20    170.55   -$2.75   ← ACTIVE, deeply underwater
CE     78,000   FROZEN (Orig)   20    84.32     36.20   +$0.96   ← 57% profit, stuck
CE     78,000   FROZEN (Adj)     4    69.50     36.20   +$0.13   ← 48% profit, stuck
CE     78,000   FROZEN (Adj)     2    60.00     36.20   +$0.05   ← 40% profit, stuck
CE     78,000   FROZEN (Adj)     4    51.00     36.20   +$0.06   ← 29% profit, stuck
CE     78,000   FROZEN (Adj)     2    52.00     36.20   +$0.03   ← 30% profit, stuck
CE     78,000   FROZEN (Adj)    32    50.50     36.20   +$0.46   ← 28% profit, stuck
─────────────────────────────────────────────────────────────
                        Total: 100 lots ← MAX CAP REACHED
                        PE:     0 lots  ← completely empty
                        Total P&L: -$1.06
```

### 1.2 The Three Compounding Problems

**Problem A — Frozen Position Dead Weight:**
64 lots are frozen at strike 78,000 with premiums at $36.20 (decaying toward 0). They are **profitable** ($1.69 total profit sitting there) but can't be closed because close-at-5 only fires at premium ≤ $5. These positions occupy 64% of the lot cap while contributing almost zero future theta.

**Problem B — One-Sided Accumulation Death Spiral:**
1. BTC moves → CE premiums rise → triggers CE aggressor
2. Algo sells PE to hedge → PE accumulates
3. BTC continues same direction → PE premiums decay → close-at-5 clears PE
4. Now algo needs to hedge again → sells more PE, but PE gets cleared again
5. Only CE positions survive → strike shifts → CE lots pile up at new strikes
6. Max lots reached on CE → algo is paralyzed

**Problem C — No Position Harvesting Between $5 and $50:**
The close-at-5 threshold ($5) is too low, and the shift_threshold ($50) triggers a new sell rather than closing old positions. The $5–$50 premium range is a **dead zone** — positions decay through it slowly without being harvested, consuming capacity for hours.

### 1.3 Why Current Mechanisms Don't Solve This

| Mechanism | Why It Fails |
|-----------|-------------|
| **Close-at-5** | Threshold too low — frozen positions at $36 won't be closed for hours |
| **Strike Shift** | Shifts the active pointer but **adds** lots at new strike — doesn't free capacity |
| **Wind-Down** | Only activates near expiry — doesn't help during the first 70% of session lifetime |
| **Position Cap** | Hard wall — blocks adjustments entirely, making the algo useless |
| **Max Adjustments** | Pauses the session — doesn't restructure positions |

---

## 2. THE SOLUTION — Three Complementary Mechanisms

### Overview

We introduce three mechanisms that work together:

| # | Mechanism | Purpose | When It Fires |
|---|-----------|---------|---------------|
| **M1** | **Profit Harvesting** | Close profitable frozen positions proactively | Every heartbeat, independent of triggers |
| **M2** | **Lot Recycling** | Consolidate when max lots blocks adjustment | When adjustment is needed but max lots reached |
| **M3** | **Smart Both-Sides Rebalancing** | Prevent one-sided accumulation | When asymmetry ratio exceeds threshold |

### Why Three Mechanisms?

- **M1 alone** would slowly free lots but too late — by the time frozen positions reach "harvest" threshold, the algo may have been blocked for multiple adjustment cycles.
- **M2 alone** only fires reactively (when already blocked) — better to prevent the blockage.
- **M3 alone** doesn't solve the frozen position drag — it rebalances but old dead-weight positions persist.
- **Together:** M1 keeps capacity flowing, M2 provides emergency relief when M1 wasn't enough, M3 prevents structural one-sidedness.

---

## 3. MECHANISM M1 — PROFIT HARVESTING (Proactive Frozen Position Cleanup)

### 3.1 Concept

Every heartbeat, scan frozen positions. If a frozen position has reached a configurable profit threshold, close it — buy it back at current premium, lock the profit, free the lot capacity. This is close-at-5 but with a **dynamic, profit-based threshold** instead of a fixed premium floor.

### 3.2 Trigger Criteria

A frozen position is eligible for harvesting if ALL of these are true:

```
1. type ∈ {'frozen', 'shifted'}         — only frozen/shifted positions
2. profit_pct ≥ harvest_profit_pct       — e.g., current ≤ 60% of entry (40%+ profit)
   where: profit_pct = (entry - current) / entry × 100
3. position_age ≥ harvest_min_age_mins   — e.g., ≥ 30 minutes old
4. capacity_pressure ≥ harvest_pressure  — total_lots / max_lots ≥ 0.6 (60%)
                                           (Don't harvest when there's plenty of room)
```

### 3.3 Position Selection

Sort eligible positions by **harvest score** (descending):

```
harvest_score = profit_pct × lot_weight
where: lot_weight = position_lots / total_side_lots
```

This prioritizes positions that are:
- **Most profitable** (least buyback cost per freed lot)
- **Largest** (free the most capacity per operation)

### 3.4 Execution Per Heartbeat

- Maximum `harvest_max_per_beat` closures per heartbeat (default: 3)
- Use existing `close_position()` from `mmm_close_at_5.py` (same buyback mechanics)
- Record as `type: 'harvest'` in activity log (distinct from close-at-5)
- Emit `mmm_harvest` WebSocket event

### 3.5 Implementation Location

**New file:** `mmm_harvester.py` (~200 lines)

**Integration point in `mmm_monitor.py`:**
- Insert between **Step 2 (close-at-5)** and **Step 2.5 (P&L recompute)**
- Same heartbeat phase as close-at-5 — both are position cleanup
- Runs BEFORE safety checks so freed capacity is visible to safety

### 3.6 Parameters (All Hot-Reload)

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `harvest_enabled` | true | bool | Enable profit harvesting |
| `harvest_profit_pct` | 40.0 | 20–80% | Min profit % to harvest |
| `harvest_min_age_mins` | 30 | 10–120 | Position minimum age |
| `harvest_pressure_threshold` | 0.6 | 0.4–0.9 | Capacity pressure to start harvesting |
| `harvest_max_per_beat` | 3 | 1–10 | Max positions to close per heartbeat |

### 3.7 Example from Live Session

Frozen positions at 78,000 with current premium $36.20:

| Position | Entry | Profit % | Lots | Score | Harvest? |
|----------|-------|----------|------|-------|----------|
| Original | $84.32 | 57% | 20 | 11.4 | ✅ YES (57% > 40%) |
| Adj | $69.50 | 48% | 4 | 1.9 | ✅ YES |
| Adj | $60.00 | 40% | 2 | 0.8 | ✅ YES (borderline) |
| Adj | $51.00 | 29% | 4 | 1.2 | ❌ NO (29% < 40%) |
| Adj | $52.00 | 30% | 2 | 0.6 | ❌ NO |
| Adj | $50.50 | 28% | 32 | 9.0 | ❌ NO |

First heartbeat: harvest the 20-lot Original (score 11.4), 4-lot Adj (1.9), 2-lot Adj (0.8)
→ **Freed 26 lots instantly**, realized ~$1.14 profit

---

## 4. MECHANISM M2 — LOT RECYCLING (Emergency Capacity Relief)

### 4.1 Concept

When an adjustment trigger fires but max lots blocks the sell, the algo consolidates its position book: buys back cheap frozen positions and uses the freed capacity + an ATM-er strike to sell fewer lots that cover both the buyback cost AND the original loss.

### 4.2 Trigger Condition

Lot recycling fires ONLY when ALL of these are true:

```
1. An adjustment trigger has fired (aggressor determined)
2. calculate_lots_to_sell() returned 0 ("position cap reached")
3. recycle_enabled == true
4. Recyclable positions exist (frozen positions with low premium)
5. No recycle cooldown is active
6. Regime is not BLOCK_ALL_SELLS
7. Margin guardian is GREEN or YELLOW (not ORANGE+)
```

### 4.3 Recyclable Position Selection

**Eligibility:**
- Position is on the **CAPPED side** (the side that's at max lots)
- Current premium ≤ `recycle_premium_ceiling` (default: 50)
- Position is NOT the currently active position
- Position is NOT original entry IF `recycle_protect_original` is true

**Sort:** Ascending by current premium (cheapest first — least cost to buyback)

**Selection:** Greedily add positions from cheapest until one of:
- Freed lots ≥ `lots_needed + recycle_free_lot_buffer`
- Or selected lots ≥ `total_lots × recycle_max_pct` (never recycle more than 50%)

### 4.4 Viability Check (Must Pass ALL)

Before executing, verify the math works:

**Check 1 — Premium ratio:**
```
new_premium / avg_recycle_premium ≥ recycle_min_premium_ratio (default: 2.5)
```
If we're buying back at $36 and new strike is only at $40, the ratio is 1.1 — not worth it. Need at least 2.5x improvement.

**Check 2 — Net lot gain:**
```python
buyback_cost = sum(current_premium[i] × lots[i] × LOT_SIZE) for recycled positions
total_to_cover = buyback_cost + original_loss_to_hedge
new_lots_needed = ceil(total_to_cover / (new_premium × LOT_SIZE) × (1 + buffer))
net_lot_gain = recycled_lots - new_lots_needed
```
Verify: `net_lot_gain ≥ recycle_min_lot_gain` (default: 5)

**Check 3 — Affordability:**
```
new_lots_needed + remaining_lots ≤ max_lots_per_side
```
The new sell must fit within the cap.

If any check fails → abort, log "recycling not viable", fall through to existing "blocked" behavior.

### 4.5 Execution — Two-Phase Atomic

**Phase A — Buyback (close recyclable positions):**
```python
for pos in recyclable_selected:
    result = await close_position(executor, initializer, session, pos)
    # Uses same close_position() as close-at-5
    # Records realized P&L, removes from positions[]
    buyback_cost += result.close_premium × pos.lots × LOT_SIZE
```

**Phase B — New Sell (open at higher-premium strike):**
```python
# Find strike via existing find_new_strike() logic (same as strike shift)
# But target premium is higher: max(shift_target_premium, 2 × avg_recycle_premium)
new_strike = find_new_strike(initializer, session, capped_side, spot_price)

total_loss = buyback_cost + original_adjustment_loss
lots_to_sell = calculate_lots(total_loss, new_strike_premium)

result = await execute_adjustment(session, capped_side, new_strike, lots_to_sell, ...)
```

**Failure handling:**
- Phase A fails → abort entirely, no state change
- Phase A succeeds, Phase B fails → lots are freed (good!), next heartbeat retries normally

### 4.6 Post-Recycle State Update

- Adjustment counter: +1
- Trigger snapshots: reset both sides
- Activity log: `type: 'recycle'` with details
- WebSocket: emit `mmm_recycle` event
- Cooldown: `recycle_cooldown_sec` (default: 300s)
- Counter: `session['recycle_count'] += 1`

### 4.7 Implementation Location

**New file:** `mmm_recycler.py` (~400 lines)

**Integration point in `mmm_monitor.py` → `_process_adjustment()`:**
- Insert at [line ~2600](after `calculate_lots_to_sell()` returns 0)
- Current code: logs "position cap reached" and returns
- New code: attempt `_process_lot_recycling()` before returning

### 4.8 Parameters (All Hot-Reload)

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `recycle_enabled` | true | bool | Enable lot recycling |
| `recycle_premium_ceiling` | 50.0 | 10–200 | Max current premium to consider recyclable |
| `recycle_min_premium_ratio` | 2.5 | 1.5–10 | Min new/old premium ratio |
| `recycle_max_pct` | 0.50 | 0.2–0.8 | Max % of lots to recycle at once |
| `recycle_free_lot_buffer` | 10 | 0–50 | Extra lots to free beyond immediate need |
| `recycle_min_lot_gain` | 5 | 1–20 | Min net lots freed to proceed |
| `recycle_cooldown_sec` | 300 | 60–600 | Cooldown between recycles |
| `recycle_protect_original` | true | bool | Never recycle original entry position |

### 4.9 Example from Live Session

**Scenario:** CE at max lots (100), PE trigger fires, algo needs to sell 30 CE lots to hedge.

Recyclable CE positions at 78,000 (current premium $36.20):
```
Select: 20 + 4 + 2 = 26 lots (cheapest-first: all are $36.20)
Buyback cost: 26 × 36.20 × 0.001 = $0.94
```

Find new CE strike closer to ATM, e.g., 71,000 with premium $200:
```
Total to cover: $0.94 (buyback) + $2.75 (loss to hedge) = $3.69
New lots: ceil($3.69 / ($200 × 0.001) × 1.05) = ceil(19.4) = 20 lots
Premium ratio: 200 / 36.20 = 5.5 ✅ (≥ 2.5)
Net lot gain: 26 - 20 = 6 ✅ (≥ 5)
```

**Result:** Freed 26 lots, used 20 → net 6 lots freed. Algo can continue adjusting.

---

## 5. MECHANISM M3 — SMART BOTH-SIDES REBALANCING

### 5.1 The One-Sided Problem

The current algo has no mechanism to prevent 100% of lots accumulating on one side. The both-sides-up check only fires when BOTH triggers activate simultaneously — a rare edge case. The common failure mode is **gradual one-sided buildup** over hours:

```
Hour 1: CE=20, PE=20   (balanced)
Hour 2: CE=30, PE=40   (PE hedging more)
Hour 3: CE=30, PE=10   (PE decayed, close-at-5 cleared)
Hour 4: CE=60, PE=20   (CE shifted + adjusted)
Hour 5: CE=80, PE=5    (PE cleared again)
Hour 6: CE=100, PE=0   ← DEAD
```

### 5.2 Rebalancing Logic

Add a **soft asymmetry intervention** that runs every heartbeat:

```python
asymmetry_ratio = max(ce_lots, pe_lots) / max(min(ce_lots, pe_lots), 1)

if asymmetry_ratio > rebalance_asymmetry_threshold:  # default: 5.0
    if dominant_side is at capacity_pressure ≥ 0.8:
        # The dominant side is hogging capacity → trigger harvest on it
        _force_harvest_on_side(dominant_side, target_lots_to_free)
```

This is NOT an automatic position action — it's a **priority booster for M1 harvesting**. When asymmetry is high, harvesting thresholds are relaxed on the dominant side:
- `harvest_profit_pct` drops from 40% → 25%
- `harvest_pressure_threshold` drops from 0.6 → 0.3
- `harvest_max_per_beat` increases from 3 → 5

### 5.3 Implementation

This is NOT a new file — it's a modifier block inside the **M1 harvester**:

```python
def get_effective_harvest_params(session, side):
    """Relax harvest thresholds when asymmetry is extreme."""
    params = session.get('params', {})
    base_profit_pct = params.get('harvest_profit_pct', 40.0)
    
    ce_lots = session.get('ce', {}).get('total_lots', 0)
    pe_lots = session.get('pe', {}).get('total_lots', 0)
    max_lots = params.get('max_lots_per_side', 100)
    
    my_lots = ce_lots if side == 'ce' else pe_lots
    other_lots = pe_lots if side == 'ce' else ce_lots
    
    asymmetry = my_lots / max(other_lots, 1)
    pressure = my_lots / max(max_lots, 1)
    
    if asymmetry > 5.0 and pressure > 0.8:
        # Extreme asymmetry — aggressively harvest dominant side
        return {
            'harvest_profit_pct': max(base_profit_pct * 0.6, 20.0),
            'harvest_max_per_beat': 5,
            'harvest_pressure_threshold': 0.3,
        }
    elif asymmetry > 3.0 and pressure > 0.6:
        # Moderate asymmetry — slightly relax
        return {
            'harvest_profit_pct': max(base_profit_pct * 0.8, 25.0),
            'harvest_max_per_beat': 4,
            'harvest_pressure_threshold': 0.5,
        }
    
    return None  # Use defaults
```

### 5.4 Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `rebalance_enabled` | true | bool | Enable asymmetry-aware harvesting |
| `rebalance_asymmetry_threshold` | 5.0 | 2–20 | Ratio to trigger relaxed harvesting |
| `rebalance_pressure_threshold` | 0.8 | 0.5–1.0 | Capacity pressure to combine with asymmetry |

---

## 6. IMPLEMENTATION PHASES

### Phase 1 — Profit Harvesting (M1) — Session 1

**Goal:** Proactive frozen position cleanup. The highest-impact, lowest-risk change.

**Files to create:**
- `mmm_harvester.py` (~200 lines)

**Files to modify:**
- `mmm_monitor.py` — add `_process_harvest()` call after close-at-5 (Step 2)
- `mmm_config.py` — add harvest parameters with validation
- `mmm_state.py` — add `DEFAULT_PARAMS` entries + `HOT_RELOAD_PARAMS`
- `mmm_websocket.py` — add `emit_harvest()` emitter
- `mmm_activity.py` — add `harvest` event type

**Frontend files:**
- `MMMSettingsDialog.js` — harvest parameter controls
- `MMMDashboard.js` / `MMMContext.js` — handle `mmm_harvest` WebSocket event
- `MMMPositionsTable.js` — show "Harvested" label on closed positions

**Testing:**
1. Create session with max_lots=20
2. Manually import positions to fill CE to 20 lots
3. Verify harvesting kicks in after positions decay
4. Verify capacity is freed and adjustments resume

### Phase 2 — Lot Recycling (M2) — Session 2

**Goal:** Emergency capital restructuring when blocked. Builds on Phase 1.

**Files to create:**
- `mmm_recycler.py` (~400 lines)

**Files to modify:**
- `mmm_monitor.py` — add recycling attempt in `_process_adjustment()` when lots = 0
- `mmm_engine.py` — add `calculate_recycle_viability()` method
- `mmm_config.py` — add recycle parameters
- `mmm_state.py` — add `DEFAULT_PARAMS` entries + `HOT_RELOAD_PARAMS`
- `mmm_websocket.py` — add `emit_recycle()` emitter
- `mmm_activity.py` — add `recycle` event type

**Frontend files:**
- `MMMSettingsDialog.js` — recycle parameter controls
- `MMMContext.js` — handle `mmm_recycle` WebSocket event
- `MMMActivityFeed.js` — show recycle events with details

**Testing:**
1. Create session with max_lots=30
2. Fill one side to capacity with mixed-premium positions
3. Trigger adjustment on opposite side
4. Verify recycling fires: buyback + new sell
5. Verify lot count drops below cap
6. Verify cooldown prevents immediate re-recycle

### Phase 3 — Asymmetry Rebalancing (M3) — Session 3

**Goal:** Prevent one-sided accumulation proactively.

**Files to modify:**
- `mmm_harvester.py` — add `get_effective_harvest_params()` asymmetry modifier
- `mmm_safety.py` — enhance `check_asymmetry()` to integrate with harvester

**Frontend files:**
- `MMMSafetyPanel.js` — show rebalancing status
- `MMMSettingsDialog.js` — rebalance parameters

**Testing:**
1. Create session, manually skew positions to CE=80, PE=5
2. Verify harvesting on CE becomes more aggressive (relaxed thresholds)
3. Verify lots freed on CE side
4. Verify asymmetry ratio improves over time

### Phase 4 — Analytics & Monitoring — Session 4

**Goal:** Track and visualize recycling effectiveness.

**Files to modify:**
- `mmm_analytics_aggregator.py` — add recycle/harvest metrics
- `mmm_analytics_storage.py` — persist metrics

**Frontend files:**
- `MMMAnalyticsPanel.js` — add harvest/recycle stats
- `MMMPositionsTable.js` — visual indicators for recyclable positions

**Metrics to track:**
- Total lots harvested/recycled per session
- Profit harvested vs. buyback cost
- Capacity utilization over time (heatmap)
- Asymmetry ratio over time
- Recycle efficiency ratio (lots freed / lots spent)

---

## 7. INTERACTION WITH EXISTING MECHANISMS

### 7.1 Heartbeat Flow (Updated)

```
Step 0:    Param reload, side reconciliation
Step 0.5:  Margin Guardian
Step 1:    Fetch CE/PE premiums
Step 1.5:  ATM checks (wind-down trigger, auto-close)
Step 2:    Close-at-5 (premium ≤ 5)
Step 2.1:  ★ PROFIT HARVESTING (M1) — close profitable frozen positions   ← NEW
Step 2.5:  Recompute unrealized P&L
Step 3:    Safety checks
Step 3.5:  Regime controls
Step 4:    Paused / both-sides-up handling
Step 4.5:  Whipsaw cooldown
Step 5:    Reversal cooldown
Step 6:    Evaluate triggers
Step 7:    Process outcome
Step 7.1:    → Normal adjustment if lots available
Step 7.2:    → ★ LOT RECYCLING (M2) if max lots blocks adjustment        ← NEW
Step 7.3:    → Log "blocked" if recycling also not viable
Step 7.5:  Perp delta hedge
Step 8:    Update P&L + peak tracking
Step 9:    Save + telemetry
```

### 7.2 Priority Matrix

| Scenario | Close-at-5 | Harvest | Recycle | Shift | Adjust |
|----------|-----------|---------|---------|-------|--------|
| Premium ≤ 5 | ✅ | — | — | — | — |
| Frozen, profitable, capacity pressure | — | ✅ | — | — | — |
| Max lots + trigger fired | — | — | ✅ | — | — |
| Hedge premium < shift_threshold | — | — | — | ✅ | — |
| Normal trigger, lots available | — | — | — | — | ✅ |
| Wind-down mode active | close-at-elevated | disabled | disabled | — | disabled |
| Regime BLOCK_ALL_SELLS | ✅ | ✅ (buy only) | ❌ | — | ❌ |
| Margin ORANGE+ | ✅ | ✅ (buy only) | ❌ | — | ❌ |

**Key interaction rules:**
- Harvesting runs on EVERY heartbeat (before safety) — it's a cleanup operation, not a trade
- Recycling ONLY fires when adjustment is blocked — it's a fallback, not a primary path
- Harvesting is **buying back** (closing positions) → always allowed even when regime blocks sells
- Recycling involves a **sell** after buyback → regime and margin checks apply to the sell leg
- During wind-down, both harvest and recycle are disabled — wind-down has its own close logic
- Close-at-5 runs first — positions at ≤ $5 are free to close (no buyback cost)

### 7.3 Interaction with Frozen Positions

**Current behavior:** Frozen positions are:
- Included in standard loss calculation (aggressor side)
- Included in reversal loss calculation (adjustment fills only, not original)
- Scanned by close-at-5 (but only closed at ≤ $5)
- Never touched otherwise

**New behavior with M1+M2:**
- Close-at-5 handles premium ≤ $5 (unchanged)
- Harvester handles premium $5–$50 range when profitable + capacity pressure
- Recycler handles the "emergency" case when above mechanisms weren't enough
- Together they eliminate the "dead zone" where positions decay slowly while consuming capacity

### 7.4 Interaction with P&L Calculations

**Critical:** When a frozen position is harvested or recycled, its realized P&L MUST be counted:

```python
realized_pnl = (entry_premium - close_premium) × lots × LOT_SIZE
session['realized_pnl'] += realized_pnl  # Positive for profitable buyback
```

This is exactly what `close_position()` already does. Both M1 and M2 use the existing close mechanics.

### 7.5 Interaction with Trigger Snapshots

**Harvesting (M1):** Does NOT reset trigger snapshots.
- Harvesting is a cleanup operation — it doesn't constitute a new hedge position.
- Triggers remain as-is. The freed capacity is available for future adjustments.

**Recycling (M2):** DOES reset trigger snapshots.
- Recycling includes a new sell (Phase B) — this IS an adjustment.
- Both sides' snapshots update to current premiums, same as any adjustment.

---

## 8. RISK ANALYSIS

### 8.1 Risks of Harvesting (M1)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Harvesting a position that later decays to 0 (missed full profit) | Low | Accept — 40% profit is already substantial. Perfect is the enemy of good |
| Slippage on buyback | Low | Use existing smart execution (mid-price). Frozen positions are far OTM with wide spreads |
| Over-harvesting when market reverses | Medium | `harvest_min_age_mins` prevents closing fresh positions. Cooldown between harvests |
| Harvesting original entry positions | Medium | `recycle_protect_original=true` by default |

### 8.2 Risks of Recycling (M2)

| Risk | Severity | Mitigation |
|------|----------|------------|
| New strike is closer to ATM → higher gamma risk | Medium | Regime gamma cap catches this. Premium ratio check ensures efficiency |
| Slippage on two transactions (buyback + sell) | Medium | Use smart execution. Phase B failure leaves capacity freed |
| Recycling at bad premium timing | Medium | `recycle_min_premium_ratio ≥ 2.5` ensures sufficient efficiency |
| Rapid repeated recycling | Low | Cooldown of 300s. Max 50% recycle per operation |
| Market reversal right after recycle | Medium | Same risk as any adjustment. Recycling doesn't increase net exposure |

### 8.3 Risks of Rebalancing (M3)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Aggressive harvesting removes protective positions | Low | Only harvests profitable positions. Unprofitable positions stay |
| Over-correction creates opposite asymmetry | Very Low | M3 only relaxes harvesting thresholds — it doesn't sell anything itself |

---

## 9. COMPLETE PARAMETER REFERENCE

### New Parameters (All Hot-Reload)

```yaml
# ── M1: Profit Harvesting ──────────────────────────────────
harvest_enabled: true                    # Enable/disable profit harvesting
harvest_profit_pct: 40.0                 # Min profit % to harvest (20-80)
harvest_min_age_mins: 30                 # Don't harvest positions younger than this (10-120)
harvest_pressure_threshold: 0.6          # Min capacity pressure to start harvesting (0.4-0.9)
harvest_max_per_beat: 3                  # Max positions to close per heartbeat (1-10)

# ── M2: Lot Recycling ─────────────────────────────────────
recycle_enabled: true                    # Enable/disable lot recycling
recycle_premium_ceiling: 50.0            # Max current premium for recyclable position (10-200)
recycle_min_premium_ratio: 2.5           # Min new/old premium ratio (1.5-10)
recycle_max_pct: 0.50                    # Max fraction of lots to recycle at once (0.2-0.8)
recycle_free_lot_buffer: 10              # Extra lots to free beyond immediate need (0-50)
recycle_min_lot_gain: 5                  # Min net lots freed to proceed (1-20)
recycle_cooldown_sec: 300                # Cooldown between recycles in seconds (60-600)
recycle_protect_original: true           # Never recycle original entry position

# ── M3: Asymmetry Rebalancing ──────────────────────────────
rebalance_enabled: true                  # Enable asymmetry-aware harvesting
rebalance_asymmetry_threshold: 5.0       # Ratio to trigger relaxed harvesting (2-20)
rebalance_pressure_threshold: 0.8        # Capacity pressure for rebalancing (0.5-1.0)
```

---

## 10. FRONTEND CHANGES

### 10.1 Positions Table Enhancements

Add visual indicators to positions:
- 🟢 **Harvestable** badge on eligible positions (green dot)
- 🔄 **Recyclable** badge on eligible positions (blue cycle icon)
- Show "harvest score" as a subtle progress bar on each position row
- "Harvested" and "Recycled" labels in the Type column for closed positions

### 10.2 Settings Dialog

Add two new sections in `MMMSettingsDialog.js`:

**"Position Lifecycle" section:**
- Harvest toggle + parameters (profit %, min age, pressure, max per beat)
- Recycle toggle + parameters (ceiling, ratio, max %, lot buffer, gain, cooldown)

**"Balance Control" section:**
- Rebalance toggle + asymmetry/pressure thresholds

### 10.3 Activity Feed

New event types in `MMMActivityFeed.js`:
- `harvest`: "Harvested 20 lots @ 78,000 (profit: $0.96, premium: $36.20 → buyback)"
- `recycle`: "Recycled 26 lots from 78,000 → sold 20 lots @ 71,000 ($200 premium)"
- `rebalance_boost`: "Asymmetry 5:1 detected — harvest thresholds relaxed on CE side"

### 10.4 Capacity Pressure Indicator

Add a **capacity gauge** to the session card header:
```
CE: ████████░░ 80/100 lots (80%)    PE: █░░░░░░░░░ 5/100 lots (5%)
```
Color: green < 60%, yellow < 80%, orange < 95%, red = 100%

---

## 11. TESTING STRATEGY

### 11.1 Unit Tests

```python
# In mmm/tests/

# test_harvester.py
- test_harvest_eligibility_criteria()
- test_harvest_score_calculation()
- test_harvest_respects_age_limit()
- test_harvest_respects_pressure_threshold()
- test_harvest_max_per_beat_limit()
- test_harvest_disabled_during_wind_down()
- test_harvest_rebalance_threshold_relaxation()

# test_recycler.py
- test_recycle_only_fires_when_blocked()
- test_recycle_viability_check_premium_ratio()
- test_recycle_viability_check_lot_gain()
- test_recycle_selects_cheapest_first()
- test_recycle_respects_max_pct()
- test_recycle_cooldown_enforcement()
- test_recycle_protect_original()
- test_recycle_phase_a_failure_aborts()
- test_recycle_phase_b_failure_safe()
```

### 11.2 Integration Tests

1. **End-to-end harvest:** Session → fill to 80% → let positions decay → verify harvest fires → verify lots freed
2. **End-to-end recycle:** Session → fill to 100% → trigger fires → verify recycle fires → verify adjustment completes
3. **Harvest + recycle cooperation:** Session → fill to 100% → harvest frees some → trigger fires → normal adjustment (not recycle)
4. **Wind-down interaction:** Session → wind-down active → verify harvest disabled
5. **Regime interaction:** Session → regime BLOCK → verify recycle sell leg blocked

### 11.3 Production Validation

Run with a **low max_lots (e.g., 30)** session alongside a traditional session for the same expiry. Compare:
- How many hours before the algo hits the wall
- Total P&L at expiry
- Number of times adjustment was blocked
- Position utilization efficiency

---

## 12. SUMMARY — EXPECTED IMPACT

| Metric | Before | After (Expected) |
|--------|--------|-------------------|
| Time before max-lot block | 2-3 hours | 8-12+ hours (or never) |
| Frozen position lot drag | 50-70% of capacity | 10-20% of capacity |
| Adjustment block events per session | 15-30 | 0-3 |
| Dead-zone positions ($5-$50 range) | Decay for hours | Harvested at 40%+ profit |
| One-sided accumulation risk | High | Low (M3 rebalancing) |
| Capital efficiency | Poor (lots wasted on dead positions) | High (continuous restructuring) |

The three mechanisms transform the algo from a **fixed-capacity system** that inevitably hits a wall into a **self-managing system** that continuously optimizes its position book for maximum theta extraction with minimum lot usage.
