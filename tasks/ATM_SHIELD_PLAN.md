# ATM Shield — Close & Retreat
## Feature Implementation Plan v5

**Created:** March 12, 2026  
**Status:** PLAN — Awaiting corrections before coding  
**Feature Priority:** HIGH — unlocks full premium collection on trend days  

---

## Table of Contents

1. [The Problem This Solves](#1-the-problem-this-solves)
2. [Core Concept](#2-core-concept)
3. [Lot Size Reference](#3-lot-size-reference)
4. [Key Design Decisions & Rationale](#4-key-design-decisions--rationale)
5. [Dynamic Scaling](#5-dynamic-scaling)
6. [Trend Guard × Shield Interaction Matrix](#6-trend-guard--shield-interaction-matrix)
7. [Full System Interaction Matrix](#7-full-system-interaction-matrix)
8. [Heartbeat Execution Order](#8-heartbeat-execution-order)
9. [Detailed Fire Sequence](#9-detailed-fire-sequence)
10. [Sympathetic Rebalance (PE when CE retreats)](#10-sympathetic-rebalance-pe-when-ce-retreats)
11. [Shield Exhaustion Behavior](#11-shield-exhaustion-behavior)
12. [close_at_ATM and wind_down_on_ATM Deferral](#12-close_at_atm-and-wind_down_on_atm-deferral)
13. [Parameters](#13-parameters)
14. [Session State Keys](#14-session-state-keys)
15. [Files to Modify](#15-files-to-modify)
16. [Per-File Implementation Details](#16-per-file-implementation-details)
17. [Edge Cases](#17-edge-cases)
18. [Why This Becomes Profitable](#18-why-this-becomes-profitable)
19. [Open Questions / Corrections Needed](#19-open-questions--corrections-needed)

---

## 1. The Problem This Solves

**Current situation:**
- Both CE and PE are sold at ~1-1.5% OTM at session start.
- BTC rallies 0.5-1%: Trend Guard T1/T2 fires → CE sells blocked (or lot-reduced). Safe PE income blocked.
- BTC rallies 1.5%+: Trend Guard T3 fires → ALL sells blocked. Zero premium income.
- BTC keeps rallying: CE eventually goes ATM → `close_at_ATM` kills everything.

**The waste:** On ~30% of trading days (mild trends 0.5-1.5%), Trend Guard blocks roughly 30-100% of premium income. The CE position isn't even in danger yet — it's 1.4% OTM. We're sacrificing PE income for no reason.

**Root cause:** Trend Guard was designed for a world without proactive ATM protection. It blocks sells defensively because there was nothing to stop spot from walking through the position. ATM Shield changes the game — it catches the CE before it becomes ATM and retreats it. So Trend Guard's defensive blocks become unnecessary (at T1/T2) or can be modified (at T3/T4) when shield has capacity.

---

## 2. Core Concept

**When spot approaches an active strike within a dynamic proximity threshold:**

1. **CLOSE (buy back)** all active positions at the endangered strike immediately
2. **RETREAT** — sell at a new strike that is `effective_target_otm` percent farther away from spot
3. **RECOVER** — split the buyback loss across both sides (30% from endangered side re-sell, 70% from safe side re-sell)
4. **SYMPATHETIC REBALANCE** — shift the safe side if its premium has decayed below `shift_threshold`

This is **not** the existing strike shift (which freezes positions and reacts to premium decay). This is a **proactive close + reposition** triggered by spot proximity to the active strike.

**Key differences from existing features:**

| Feature | Trigger | Action on endangered side | Requires new sell? |
|---|---|---|---|
| `close_at_ATM` | Spot within 0.5% of **original** strike | Close **all** positions, stop | No |
| `wind_down_on_ATM` | Spot within 0.5% of **original** strike | Progressive LIFO buyback | No |
| **ATM Shield** | Spot within `proximity_pct` of **active** strike | Close, reposition at OTM strike | **Yes** |
| Proactive Shift | Premium decays below `shift_threshold` | Freeze + sell at new premium | Yes |

Shield fires **before** position goes ATM. close_at_ATM fires **at** ATM. They are complementary with deferral logic (see Section 12).

---

## 3. Lot Size Reference

**1 lot = 0.001 BTC on Delta Exchange India.**

All lot calculations flow through `calculate_lots_to_sell()` in `mmm_engine.py`, which uses `LOT_SIZE_BTC = 0.001` from `mmm_constants.py`.

Formula:
```
raw_lots = loss_to_cover / (premium × LOT_SIZE_BTC) × (1 + buffer_pct)
lots = max(ceil(raw_lots), 1)
```

Shield does NOT do its own lot math. It calls `calculate_lots_to_sell()` which automatically applies:
- Premium buffer (5% default)
- Position cap (`max_lots_per_side`)
- Trend boost (if enabled, for safe side)
- Total exposure ceiling

---

## 4. Key Design Decisions & Rationale

### 4.1 Close via `close_position()` from mmm_close_at_5.py

**Why:** Battle-tested function that handles:
- Double-close guard (`_being_closed` flag prevents duplicate orders)
- Exchange BUY order placement
- State cleanup (removes position from ledger)
- Realized P&L calculation
- Error handling and retry logic

### 4.2 Re-sell via `execute_adjustment()` from mmm_engine.py

**Why:** Handles pending order registry, exchange SELL order, fill recording, trigger snapshot update. All existing safety gates apply (position cap, velocity limiter, etc.).

### 4.3 Sympathetic shift via `_process_strike_shift()` from mmm_monitor.py

**Why:** Existing function that freezes old position (cheaply closed by close-at-5/M1 later) and sells at new strike. Handles all edge cases (no strike found, cap hit, etc.). Safer than doing a close+new-sell directly.

### 4.4 New strike via `find_new_strike()` from mmm_strike_shift.py

**Why:** Already handles chain scanning, premium floor (`shift_threshold`), and sorting by `shift_target_premium` proximity. ATM Shield adds one filter: only consider strikes beyond `effective_target_otm` distance from spot.

### 4.5 Shield RE-SELL on endangered side is EXEMPT from BLOCK_CE/PE_SELLS

**Why this must be true:** At Trend T3/T4, regime blocks CE sells (`BLOCK_CE_SELLS`). If shield closes CE positions but cannot re-sell CE, CE goes to 0 lots. The one-side-close guard immediately **PAUSES** the session. This defeats the purpose of the shield entirely.

Shield's CE re-sell at T3/T4 is a **defensive repositioning** (far OTM, 2%+ away from spot), not an aggressive new directional bet. The regime block was designed for the latter. Exemption is safe here.

**What is NOT exempt:** Vol/gamma regime blocks (BLOCK_ALL_SELLS from vol HIGH or gamma HARD). These protect against entirely different risks.

### 4.6 Default OFF in DEFAULT_PARAMS

**Why:** This feature places real exchange orders — BUY (close) + SELL (re-sell). A proximity miscalculation, chain scanning failure, or edge case in the first version means unnecessary real-money orders. Start conservatively: `atm_shield_enabled: False`. User enables it manually on session creation (one click), validates 2-3 sessions, then we change the default to True.

---

## 5. Dynamic Scaling

### 5.1 Time-to-Expiry Multiplier

Reuses existing `_get_minutes_to_expiry()` from `mmm_monitor.py`.

```python
minutes = self._get_minutes_to_expiry() or 360
hours = max(minutes / 60.0, 0.5)  # floor at 30 minutes to avoid division issues
time_mult = min(3.0, max(1.0, 3.0 / hours))
```

**Rationale:** With 30 minutes to expiry, gamma is massive. A 1% OTM position can become ATM in 2-3 minutes during a volatile move. The shield needs to fire earlier AND retreat farther.

| Hours to Expiry | time_mult | Effective Proximity (base 0.5%) | Effective Target OTM (base 1%, 1st fire) |
|---|---|---|---|
| 6+ hours | 1.0× | 0.5% | 1.0% |
| 3 hours | 1.0× | 0.5% | 1.0% |
| 2 hours | 1.5× | 0.75% | 1.5% |
| 1 hour | 3.0× | 1.5% | 3.0% |
| 30 min | 3.0× (cap) | 1.5% | 3.0% |

### 5.2 Progressive Widening Per Side

Each successive shield fire on the same side retreats **50% farther** OTM, because each fire indicates the market is in a stronger directional trend.

```python
shield_count = session.get(f'_atm_shield_count_{side}', 0)  # 0 for first fire
progressive_mult = 1.0 + (shield_count * 0.5)  # 1.0 → 1.5 → 2.0
```

### 5.3 Combined Formula

```
effective_proximity  = base_proximity_pct  × time_mult
effective_target_otm = base_target_otm_pct × time_mult × progressive_mult
```

**Full table (base_proximity=0.5%, base_target_otm=1.0%):**

| Fire # | 6hr+ | 3hr | 2hr | 1hr | 30min |
|---|---|---|---|---|---|
| **1st proximity** | 0.50% | 0.50% | 0.75% | 1.50% | 1.50% |
| **1st target OTM** | 1.00% | 1.00% | 1.50% | 3.00% | 3.00% |
| **2nd target OTM** | 1.50% | 1.50% | 2.25% | 4.50% | 4.50% |
| **3rd target OTM** | 2.00% | 2.00% | 3.00% | 6.00% | 6.00% |
| **4th+ (exhausted)** | Wind-down | Wind-down | Wind-down | Wind-down | Wind-down |

**Example:** 2nd shield on CE, 2 hours before expiry, BTC at $72,000:
- Effective OTM = 1.0% × 1.5 × 1.5 = 2.25%
- Min new CE strike = $72,000 × 1.0225 = $73,620
- Chain scan picks nearest strike ≥ $73,620 with premium ≥ `shift_threshold`

---

## 6. Trend Guard × Shield Interaction Matrix

### 6.1 Current Behavior (Without Shield)

| Tier | Spot Move | Regime Action | Effect |
|---|---|---|---|
| T0 NORMAL | <0.5% | `ACTION_NORMAL` | Both sides sell fully |
| T1 ALERT | 0.5-1% | `ACTION_WARN` | 30% lot reduction via `calculate_lots_to_sell()` |
| T2 GUARD | 1-1.5% | `BLOCK_CE_SELLS` (up) / `BLOCK_PE_SELLS` (down) | Dangerous side sells blocked |
| T3 BLOCK | 1.5-2% | `BLOCK_ALL_SELLS` (or `BLOCK_CE` if trend_boost) | All sells blocked |
| T4 WIND-DOWN | 2%+ | `BLOCK_ALL_SELLS` + wind-down triggered | Everything stops |

### 6.2 New Behavior When ATM Shield ON with Capacity

| Tier | Move | Shield Action | Regime Action Produced |
|---|---|---|---|
| T1 ALERT | 0.5-1% | No lot reduction | **`ACTION_NORMAL`** — sell both sides at full quantity |
| T2 GUARD | 1-1.5% | Override directional block | **`ACTION_NORMAL`** — sell both sides at full quantity |
| T3 BLOCK | 1.5-2% | Block dangerous side only | **`BLOCK_CE_SELLS`** (up) / **`BLOCK_PE_SELLS`** (down) |
| T4 WIND-DOWN | 2%+ | Block dangerous side, no wind-down trigger | **`BLOCK_CE_SELLS`** (up) / **`BLOCK_PE_SELLS`** (down) |

**Critical:** Shield RE-SELL on the endangered side at T3/T4 is **exempt** from the `BLOCK_CE/PE_SELLS` regime action (see Section 4.5).

### 6.3 Logic in `_compute_regime_action()` (mmm_regime.py)

```python
# --- Insert AFTER existing gamma checks, BEFORE trend tier checks ---

shield_on = params.get('atm_shield_enabled', False)
if shield_on and trend_tier >= TREND_TIER_ALERT:
    trend_dir = session.get('_trend_direction', 'none')
    if trend_dir in ('up', 'down'):
        endangered = 'ce' if trend_dir == 'up' else 'pe'
        count = session.get(f'_atm_shield_count_{endangered}', 0)
        max_fires = params.get('atm_shield_max_per_session', 3)
        if count < max_fires:
            # Shield has capacity — modify trend tier behavior
            if trend_tier <= TREND_TIER_GUARD:  # T1 or T2
                return ACTION_NORMAL              # Both sides sell
            else:                                 # T3 or T4
                if trend_dir == 'up':
                    return ACTION_BLOCK_CE_SELLS  # Protect dangerous side, PE sells free
                elif trend_dir == 'down':
                    return ACTION_BLOCK_PE_SELLS  # Protect dangerous side, CE sells free
        # Shield exhausted → fall through to original behavior

# --- Continuation of existing tier logic (unchanged) ---
```

### 6.4 Lot Reduction Change in `calculate_lots_to_sell()` (mmm_engine.py)

In the `elif trend_tier >= 1:` block (T1 lot reduction):

```python
elif trend_tier >= 1:
    shield_on = params.get('atm_shield_enabled', False)
    if shield_on:
        # T1 lot reduction disabled — shield manages ATM risk
        session['_trend_boost_active'] = False
        session['_trend_boost_mult'] = 1.0
    else:
        # Original: 30% lot reduction
        lot_reduction = params.get('trend_tier1_lot_reduction', 0.30)
        multiplier = max(1.0 - lot_reduction, 0.1)
        original_lots = lots_to_sell
        lots_to_sell = max(math.ceil(lots_to_sell * multiplier), 1)
        ...
```

**Note:** The TREND BOOST path (T1+ with `trend_boost_enabled`, safe side boost) runs BEFORE this block and is **completely unchanged**. Shield enabling doesn't affect trend boost — they work independently.

---

## 7. Full System Interaction Matrix

| System | State | CLOSE | Endangered RE-SELL | Safe RE-SELL | Sympathetic SHIFT | Notes |
|---|---|---|---|---|---|---|
| **Trend Guard** | T0-T2 (with shield) | Yes | Yes | Yes | Yes | Regime → NORMAL |
| | T3-T4 (with shield) | Yes | **Yes (exempt from BLOCK_CE/PE)** | Yes (safe side unblocked) | Yes | Only dangerous side blocked |
| | Any (shield exhausted) | Skip shield entirely | — | — | — | Revert to original behavior |
| **Margin Guardian** | GREEN | Yes | Yes | Yes | Yes | Normal |
| | YELLOW | Yes | No | No | No | Close only. `_margin_block_sells` flag |
| | ORANGE | Yes | No | No | No | Wind-down forced |
| | RED/CRITICAL | **Skip shield** | — | — | — | Emergency handler owns this |
| **Vol Regime** | NORMAL | Yes | Yes | Yes | Yes | Normal |
| | ELEVATED | Yes | No | No | No | Not overridden by shield |
| | HIGH | Yes | No | No | No | Not overridden by shield |
| **Gamma Cap** | NORMAL/SOFT | Yes | Yes | Yes | Yes | Normal |
| | HARD/EMERGENCY | Yes | No | No | No | Not overridden by shield |
| **Wind-down** | Active | Yes | No | No | No | Close accelerates wind-down goal |
| **Whipsaw Guard** | Any score | Yes | Yes | Yes | Yes | Shield actions NOT counted toward score |
| **close_at_ATM** | Enabled | Deferred | Deferred | — | — | Shield fires first (Section 12) |
| **wind_down_on_ATM** | Enabled | Deferred | — | — | — | Shield fires first (Section 12) |
| **Proactive Shift** | Already shifted this beat on same side | **Skip this side** | — | — | — | `_proactive_shifted_{side}` flag |
| **Near-expiry** | stop_adjustment_mins | Yes | No | No | No | No new positions in final minutes |
| | auto_close_mins | **Skip shield** | — | — | — | Not worth repositioning when auto-close imminent |
| **Position Cap** | — | — | Enforced | Enforced | Enforced | `calculate_lots_to_sell` checks cap |
| **FSU Scale-up** | — | N/A | N/A | N/A | N/A | Skipped when `_atm_shield_fired` set |

---

## 8. Heartbeat Execution Order

### Current Heartbeat (relevant steps)

```
Margin Guardian check (RED/CRITICAL → early exit)
Fetch premiums (ce_now, pe_now)
Step 1:    ATM wind-down check (wind_down_on_ATM)
Step 1:    ATM auto-close check (close_at_ATM)
Step 1.5:  Proactive shift scan (_proactive_shift_scan)
Step 2:    Close-at-5 (_process_close_at_5)
Step 2.1:  M1 Profit Harvest (_process_harvest)
Step 2.5:  One-side-close guard
Step 3:    Safety checks (max-loss, trailing stop, whipsaw, etc.)
Step 3.5:  Regime controls (vol, gamma, trend → _regime_action)
Step 4:    Paused state / both-sides-up handler
Step 5:    Cooldown check
Step 6:    Evaluate triggers (evaluate_triggers)
Step 7:    Process outcome (OUTCOME_CE/PE/BOTH/NONE)
Step 7.5:  Perp hedge
Step 8:    P&L update, save, emit heartbeat
```

### New Heartbeat with ATM Shield

```
Margin Guardian check (RED/CRITICAL → early exit)
Fetch premiums (ce_now, pe_now)
Step 1:    ATM wind-down check → [DEFERRED if shield has capacity]
Step 1:    ATM auto-close check → [DEFERRED if shield has capacity]
Step 1.5:  Proactive shift scan (_proactive_shift_scan)
Step 2:    Close-at-5 (_process_close_at_5)
Step 2.1:  M1 Profit Harvest (_process_harvest)
Step 2.5:  One-side-close guard
Step 3:    Safety checks (no change)
Step 3.5:  Regime controls → [shield-aware: T1/T2=NORMAL, T3/T4=BLOCK_CE/PE]
Step 4:    Paused check / both-sides-up
Step 5:    Cooldown check
→ Step 5.5: ATM SHIELD [NEW]
             a. Check if enabled + not in auto_close_mins window
             b. Fetch spot price
             c. For each side: compute effective_proximity, check if endangered
             d. If both sides simultaneously endangered → SKIP (defer to close_at_ATM)
             e. Fire on endangered side:
                1. Gate checks (margin RED? skip. Wind-down? close-only. Cooldown? skip.)
                2. CLOSE all active positions at endangered strike
                3. FIND new OTM strike (effective_target_otm distance)
                4. RE-SELL on endangered side (exempt from BLOCK_CE/PE)
                5. RE-SELL on safe side (normal lot calculation)
                6. SYMPATHETIC REBALANCE safe side if premium < shift_threshold
                7. Update state (_atm_shield_count, _atm_shield_last_fire, _atm_shield_fired)
Step 6:    Evaluate triggers → SKIPPED if _atm_shield_fired=True
Step 7:    Process outcome (OUTCOME_CE/PE/BOTH/NONE) → SKIPPED if _atm_shield_fired=True
Step 7.5:  Perp hedge (runs always)
Step 8:    P&L update, save, emit heartbeat (runs always)
```

**Why trigger evaluation is skipped when shield fires:**  
After shield closes and re-sells, trigger snapshots for both sides have been reset. If triggers run in the same beat, they evaluate against stale snapshots and will likely produce false OUTCOME_CE/PE signals. Skip this beat's trigger evaluation — next beat is clean.

---

## 9. Detailed Fire Sequence

### 9.1 Proximity Check

```python
spot = await self._fetch_spot_price()
minutes = self._get_minutes_to_expiry() or 360
hours = max(minutes / 60.0, 0.5)
time_mult = min(3.0, max(1.0, 3.0 / hours))

effective_proximity_pct = params.get('atm_shield_proximity_pct', 0.5) * time_mult

for side in ['ce', 'pe']:
    side_state = session.get(side, {})
    active_lots = side_state.get('active_lots', 0)
    active_strike = side_state.get('active_strike', 0)
    
    if active_lots <= 0 or active_strike <= 0:
        continue
    
    if side == 'ce':
        # CE endangered when spot approaches from below
        distance_pct = (active_strike - spot) / spot * 100
    else:
        # PE endangered when spot approaches from above
        distance_pct = (spot - active_strike) / spot * 100
    
    if distance_pct <= effective_proximity_pct:
        endangered_side = side
        break  # Only fire on one side per beat
```

### 9.2 Gate Checks (abort if any fail)

```
1. atm_shield_enabled?
2. Session paused or strategy_status not RUNNING?
3. Margin tier RED or CRITICAL?
4. Within auto_close_mins window?  (shield too late, let auto-close handle)
5. Cooldown elapsed?  (now - _atm_shield_last_fire_{side} >= cooldown_mins)
6. Shield capacity remaining?  (_atm_shield_count_{side} < max_per_session)
7. Both CE and PE simultaneously endangered?   (defer to close_at_ATM — rare straddle ATM case)
8. Side already proactive-shifted this beat?  (_proactive_shifted_{side} flag)
```

### 9.3 Close Step

```python
# Get all active positions on the endangered side
positions_to_close = [
    p for p in session[side].get('positions', [])
    if p.get('status') == 'active' and not p.get('_being_closed')
]

total_realized_loss = 0.0
total_closed_lots = 0
for pos in positions_to_close:
    result = await close_position(executor, initializer, session, pos,
                                  pnl_attribution_key='atm_shield')
    if result.get('success'):
        buyback_premium = result.get('close_premium', 0)
        entry_premium = pos.get('entry_premium', 0)
        lots = pos.get('lots', 0)
        total_closed_lots += lots
        total_realized_loss += (buyback_premium - entry_premium) * lots * LOT_SIZE_BTC
```

**Note:** `total_realized_loss` can be negative (rare — premium decayed since sell, buyback cheaper). In that case, `max(total_realized_loss, 0)` = 0 → no recovery lots, but the `base_lots` (original position) are still re-sold at the new strike. The position is correctly shifted even when there's no loss to recover.

### 9.4 Find New Strike

```python
shield_count = session.get(f'_atm_shield_count_{side}', 0)
progressive_mult = 1.0 + (shield_count * 0.5)  # 1st fire=1.0, 2nd=1.5, 3rd=2.0

effective_target_otm_pct = (
    params.get('atm_shield_target_otm_pct', 1.0)
    * time_mult
    * progressive_mult
)

# min_distance from spot that the new strike must be
min_distance = spot * effective_target_otm_pct / 100.0

# Call find_new_strike with min_otm_distance filter
new_strike, new_premium = find_new_strike(
    initializer=initializer,
    session=session,
    side=side,
    spot_price=spot,
    min_otm_distance=min_distance,   # NEW param added to find_new_strike
)
```

**If no viable strike found** (no strike at target distance with premium ≥ shift_threshold):
- Log warning
- Skip re-sell on this side
- Absorb the loss — better than holding ATM risk
- Sympathetic rebalance still runs for safe side

### 9.5 Re-Sell Step — Full Position Shift + Loss Recovery

**Critical concept:** Shield is a SHIFT, not just a hedge. The original position must be re-established at the new strike, PLUS additional lots to recover the buyback loss.

**Example:** CE had 10 lots sold at $100. Shield fires when premium=$200.
- Buyback loss = ($200 - $100) × 0.001 × 10 = $1.00
- New OTM strike premium = $80
- CE re-sell: **10 lots (position shift)** + ceil($0.30 / ($80 × 0.001)) = 10 + 4 = **14 lots**
- PE re-sell: ceil($0.70 / ($60 × 0.001)) = **12 lots** (loss recovery only)

Without the position shift, CE would have only 4 lots vs PE's 22+ lots — massive asymmetry and zero premium collection on CE.

```python
loss_split_agr = params.get('atm_shield_loss_split_aggressor', 0.3)

# --- Endangered side re-sell (exempt from BLOCK_CE/PE_SELLS) ---
if new_strike is not None:
    sells_possible = not (
        margin_wind_down                           # ORANGE+
        or margin_block_sells                      # YELLOW
        or is_wind_down_active(session)            # Wind-down mode
        or near_stop_adjustment_mins               # Near expiry
        or regime_vol_gamma_blocked                # Vol HIGH or Gamma HARD (NOT trend)
    )
    # Trend regime BLOCK_CE/PE_SELLS is specifically EXEMPT here
    
    if sells_possible:
        # 1. POSITION SHIFT: re-establish original lot count at new strike
        base_lots = total_closed_lots  # lots that were just bought back (e.g. 10)
        
        # 2. LOSS RECOVERY: additional lots to cover 30% of buyback loss
        loss_share_agr = max(total_realized_loss, 0) * loss_split_agr
        if loss_share_agr > 0 and new_premium > 0:
            recovery_lots = max(math.ceil(
                loss_share_agr / (new_premium * LOT_SIZE_BTC)
            ), 0)
        else:
            recovery_lots = 0
        
        # 3. TOTAL: shifted lots + recovery lots (still subject to position cap)
        total_lots_agr = base_lots + recovery_lots
        
        # Apply position cap from calculate_lots_to_sell constraints
        max_lots = params.get('max_lots_per_side', 100)
        current_lots = session[side].get('active_lots', 0)
        cap_remaining = max(max_lots - current_lots, 0)
        total_lots_agr = min(total_lots_agr, cap_remaining)
        
        if total_lots_agr > 0:
            await engine.execute_adjustment(
                session, side, new_strike, total_lots_agr,
                ce_now, pe_now, adj_type='atm_shield'
            )

# --- Safe side re-sell (normal regime rules, LOSS RECOVERY ONLY) ---
# Safe side does NOT get position-shifted — only extra lots for 70% loss recovery
safe_side = 'pe' if side == 'ce' else 'ce'
safe_active_strike = session[safe_side].get('active_strike', 0)
safe_premium = pe_now if safe_side == 'pe' else ce_now

if safe_active_strike > 0 and safe_premium > 0:
    blocked, _ = regime_engine.should_block_sell(session, safe_side)
    if not blocked and not margin_block_sells and not margin_wind_down:
        loss_share_safe = max(total_realized_loss, 0) * (1.0 - loss_split_agr)
        lots_safe, msg_safe, cap_hit_safe = engine.calculate_lots_to_sell(
            session, safe_side, loss_share_safe, safe_premium
        )
        if lots_safe > 0:
            await engine.execute_adjustment(
                session, safe_side, safe_active_strike, lots_safe,
                ce_now, pe_now, adj_type='atm_shield'
            )
```

### 9.6 Update State

```python
session[f'_atm_shield_count_{side}'] = shield_count + 1
session[f'_atm_shield_last_fire_{side}'] = datetime.now(timezone.utc).isoformat()
session['_atm_shield_fired'] = True  # Skips triggers + FSU this beat

# Log + emit
log_activity('atm_shield', f'🛡️ ATM Shield: {side.upper()} @ {endangered_strike:.0f} ...',
             sid, 'warning', {...})
emit_atm_shield(sid, {...})

# Exhaustion check
if session[f'_atm_shield_count_{side}'] >= max_per_session:
    log.warning(f"ATM Shield exhausted for {side.upper()} — wind-down mode activated")
    session['_atm_shield_exhausted_{side}'] = True
    # Regime reverts to original behavior on next beats
```

---

## 10. Sympathetic Rebalance (PE when CE retreats)

### The Problem

BTC rallies. CE at $73,000 gets shielded → retreats to $73,500.

Meanwhile, PE at $71,000 is now 3.6% OTM. Premium has decayed to $12 (was $90 at sell). In 1-2 more heartbeats, premium drops below `close_at_threshold` ($5) → close-at-5 CLOSES the PE position → one-side-close guard sees CE=2 lots, PE=0 lots → **SESSION PAUSED.**

### The Solution

Immediately after shield fires on CE, check PE:

```python
safe_side = 'pe' if side == 'ce' else 'ce'
safe_premium = pe_now if safe_side == 'pe' else ce_now
safe_active_lots = session[safe_side].get('active_lots', 0)
shift_threshold = params.get('shift_threshold', 50.0)

if (safe_active_lots > 0 
    and safe_premium < shift_threshold
    and not session.get(f'_proactive_shifted_{safe_side}')):
    
    log.info(f"ATM Shield: sympathetic rebalance {safe_side.upper()} "
             f"(premium ${safe_premium:.2f} < threshold ${shift_threshold:.0f})")
    await self._process_strike_shift(safe_side, 0.0, ce_now, pe_now)
    session[f'_proactive_shifted_{safe_side}'] = True
```

**Result:** Old PE at $71,000 is frozen (premium $12 → close-at-5 handles it cheaply next beat). New PE sold at ~$71,800 (closer to spot, fresh premium $80+). Both sides now symmetrically positioned around current spot.

**Why `_process_strike_shift()` over direct close+sell:**
- Freezes vs closes: freeze is cheaper (old PE at $12 will expire worthless or close-at-5 buys it for $12 total; no exchange close order needed immediately)
- Handles "no new strike found" gracefully
- Updates trigger snapshots correctly
- Battle-tested edge case handling

---

## 11. Shield Exhaustion Behavior

When `_atm_shield_count_{side} >= atm_shield_max_per_session`:

1. **No more shield fires for that side** — `_atm_shield_exhausted_{side}` = True
2. **Regime reverts to original behavior** — the shield-aware override in `_compute_regime_action()` checks capacity first; if exhausted, falls through to original tier logic
3. **close_at_ATM resumes** — deferral logic checks shield capacity; exhausted → fires normally
4. **wind_down_on_ATM resumes** — same
5. **T1 lot reduction resumes**
6. **T3/T4 BLOCK_ALL_SELLS resumes** (or BLOCK_CE if trend_boost_enabled)
7. **T4 wind-down trigger resumes**

The last retreated position sits at `base_target_otm × time_mult × 2.0` distance from spot — typically 2-6%+ OTM. This provides meaningful buffer for the existing systems to manage the situation.

**Safe side behavior:** Unaffected by shield exhaustion on the other side. PE continues selling at full capacity as long as PE shield (if needed) has capacity.

---

## 12. close_at_ATM and wind_down_on_ATM Deferral

### The Race Condition

```
Step 1. close_at_ATM fires at 0.5% proximity to ORIGINAL strike
Step 5.5. Shield fires at 0.5% proximity to ACTIVE strike (= original strike, first fire)
```

On the FIRST shield fire, active_strike == original_strike. So close_at_ATM fires first at Step 1 and **CLOSES ALL POSITIONS** before shield runs. Shield never gets a chance.

### The Fix

In Step 1 (close_at_ATM block in mmm_monitor.py):

```python
if params.get('close_at_atm', False):
    if not session.get('_atm_close_triggered'):
        # ... compute atm_triggered_side as currently ...
        if atm_triggered_side:
            # ATM Shield deferral check
            if params.get('atm_shield_enabled', False):
                _endangered = atm_triggered_side.lower()
                _count = session.get(f'_atm_shield_count_{_endangered}', 0)
                _max = params.get('atm_shield_max_per_session', 3)
                if _count < _max:
                    log.info(f"[{sid}] close_at_ATM deferred to ATM Shield "
                             f"(capacity: {_max - _count} fires remaining)")
                    # Skip this beat — shield handles at Step 5.5
                    pass
                else:
                    # Shield exhausted — close_at_ATM fires as normal
                    ... existing close logic ...
            else:
                # Shield not enabled — close_at_ATM fires as normal
                ... existing close logic ...
```

Same pattern for wind_down_on_ATM.

### State After First Shield Fire

After shield fire #1, `active_strike` moves from $73,000 to $73,500. Now close_at_ATM checks `original_strike` ($73,000) vs current spot. If spot is at $72,640, spot is **below** original strike — close_at_ATM no longer triggers (it would need spot ≥ $73,000 × 0.995 = $72,635). So the deferral handle resolves naturally after the first fire.

---

## 13. Parameters

| Parameter | Type | Default | Hot-reload | Range | Description |
|---|---|---|---|---|---|
| `atm_shield_enabled` | bool | `False` | Yes | true/false | Master switch. Enable manually per session until feature validated. |
| `atm_shield_proximity_pct` | float | `0.5` | Yes | 0.1–5.0 | Base % from active strike that triggers shield. Scaled by time-to-expiry multiplier. At 6hr+: fires when spot within 0.5% of strike. |
| `atm_shield_target_otm_pct` | float | `1.0` | Yes | 0.1–10.0 | Base target % OTM for new strike after retreat. Scaled by time multiplier and progressive widening. |
| `atm_shield_loss_split_aggressor` | float | `0.3` | Yes | 0.0–1.0 | Fraction of buyback loss recovered from endangered-side re-sell. Remaining (0.7) from safe-side re-sell. |
| `atm_shield_max_per_session` | int | `3` | Yes | 1–10 | Max shield fires per side per session. After exhaustion, reverts to original trend guard behavior. |
| `atm_shield_cooldown_mins` | int | `10` | Yes | 0–60 | Minimum minutes between shield fires on the same side. Prevents rapid-fire whipsaw. |

**Hardcoded constants (not configurable — kept simple for v1):**
- `time_mult = min(3.0, max(1.0, 3.0 / max(hours_to_expiry, 0.5)))` 
- `progressive_step = 0.5` (each successive fire widens OTM by 50% of base)
- Reuses existing `shift_threshold` and `shift_target_premium` params for new strike selection

---

## 14. Session State Keys

All session state keys used by ATM Shield:

| Key | Type | Description |
|---|---|---|
| `_atm_shield_count_ce` | int | Number of shield fires on CE side this session. 0 if never fired. |
| `_atm_shield_count_pe` | int | Number of shield fires on PE side this session. 0 if never fired. |
| `_atm_shield_last_fire_ce` | str (ISO) | Timestamp of last CE shield fire. Used for cooldown check. |
| `_atm_shield_last_fire_pe` | str (ISO) | Timestamp of last PE shield fire. Used for cooldown check. |
| `_atm_shield_exhausted_ce` | bool | True if CE shield has reached max_per_session. |
| `_atm_shield_exhausted_pe` | bool | True if PE shield has reached max_per_session. |
| `_atm_shield_fired` | bool | Set when shield fires this beat. Cleared at start of next beat. Causes triggers/FSU to skip. |

**Migration:** New keys — no migration needed. Default value when absent = 0 / None.

---

## 15. Files to Modify

| # | File | Type | Lines Est. | Change Summary |
|---|---|---|---|---|
| 1 | `mmm_atm_shield.py` | **NEW** | ~350 | Core shield logic: proximity check, dynamic scaling, close+retreat+re-sell, sympathetic rebalance |
| 2 | `mmm_monitor.py` | Modify | ~45 | Step 5.5 hook, close_at_ATM deferral, wind_down_on_ATM deferral, `_atm_shield_fired` skip, import |
| 3 | `mmm_regime.py` | Modify | ~25 | Shield-aware `_compute_regime_action()`: T1/T2→NORMAL, T3/T4→BLOCK_CE/PE only |
| 4 | `mmm_engine.py` | Modify | ~8 | Skip T1 lot reduction when shield ON in `calculate_lots_to_sell()` |
| 5 | `mmm_state.py` | Modify | ~14 | 6 params in DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| 6 | `mmm_config.py` | Modify | ~42 | 6 PARAM_RULES + descriptions + validation |
| 7 | `mmm_activity.py` | Modify | ~2 | Add `'atm_shield': 'ATM Shield'` to ACTIVITY_TYPES |
| 8 | `mmm_websocket.py` | Modify | ~18 | Add `emit_atm_shield(sid, data)` function |
| 9 | `MMMSettingsDialog.js` | Modify | ~55 | ATM Shield settings section in WebUI |
| 10 | `mmm_strike_shift.py` | Modify | ~12 | Add `min_otm_distance` param to `find_new_strike()` |

---

## 16. Per-File Implementation Details

### 16.1 mmm_atm_shield.py (NEW)

```
Sections:
  - Module docstring
  - Imports (close_position, calculate_lots_to_sell, execute_adjustment,
              _process_strike_shift, find_new_strike, LOT_SIZE_BTC, log_activity,
              is_wind_down_active, _get_minutes_to_expiry)
  - _compute_time_mult(minutes_to_expiry) → float
  - _compute_effective_proximity(session, params, time_mult) → float
  - _check_shield_gates(session, side, margin_tier, minutes_to_expiry) → (bool, str)
  - _find_new_strike_for_shield(initializer, session, side, spot, time_mult, shield_count)
      → (strike: float | None, premium: float)
  - _recover_loss(session, engine, …) (manages the re-sell math)
  - check_atm_proximity(session, spot, params, minutes_to_expiry)
      → (endangered_side: str | None, distance_pct: float)
  - async execute_atm_shield(monitor, ce_now, pe_now) → bool
      (returns True if fired, False if no fire needed)
```

### 16.2 mmm_monitor.py

**Change 1 — Import:**
```python
from .mmm_atm_shield import execute_atm_shield
```

**Change 2 — close_at_ATM deferral block (Step 1):**
Add 8-line deferral check before the existing close logic (inside `if atm_triggered_side:` block).

**Change 3 — wind_down_on_ATM deferral block (Step 1):**
Same pattern as close_at_ATM deferral.

**Change 4 — Step 5.5 insertion:**
After Step 5 (cooldown check), before Step 6 (evaluate_triggers):
```python
# Step 5.5: ATM Shield — proactive close & retreat
if not _skip_to_pnl and params.get('atm_shield_enabled', False):
    try:
        _shield_fired = await execute_atm_shield(self, ce_now, pe_now)
        if _shield_fired:
            session['_atm_shield_fired'] = True
    except Exception as _shield_err:
        log.error(f"[{sid}] ATM Shield error: {_shield_err}", exc_info=True)
        # Non-fatal — continue without shield this beat
```

**Change 5 — Skip triggers when shield fired:**
```python
if not _skip_to_pnl:
    # Clear per-beat shield flag
    shield_fired_this_beat = session.pop('_atm_shield_fired', False)
    
    if shield_fired_this_beat:
        log.info(f"[{sid}] Shield fired this beat — skipping trigger evaluation")
        # Fall through to Step 7.5/8 (P&L, perp, save)
    else:
        # Step 6: Evaluate triggers (§7) — normal path
        ...
```

### 16.3 mmm_regime.py

**Change location:** In `_compute_regime_action()`, after the existing gamma emergency check (`if gamma_regime == GAMMA_EMERGENCY: return ACTION_FORCE_REDUCE`) and BEFORE the vol HIGH checks.

Insert the shield-aware trend override block (code shown in Section 6.3).

### 16.4 mmm_engine.py

**Change location:** In `calculate_lots_to_sell()`, in the T1 lot reduction block (`elif trend_tier >= 1:`). Add the shield check (code shown in Section 6.4).

### 16.5 mmm_state.py — DEFAULT_PARAMS block

```python
# ATM Shield (added March 2026)
'atm_shield_enabled': False,
'atm_shield_proximity_pct': 0.5,
'atm_shield_target_otm_pct': 1.0,
'atm_shield_loss_split_aggressor': 0.3,
'atm_shield_max_per_session': 3,
'atm_shield_cooldown_mins': 10,
```

Also add all 6 to HOT_RELOAD_PARAMS list.

### 16.6 mmm_config.py — PARAM_RULES

```python
'atm_shield_enabled':              ParamRule(bool,  None,  None,  'ATM Shield master switch'),
'atm_shield_proximity_pct':        ParamRule(float, 0.1,   5.0,   'Base % from active strike to trigger shield'),
'atm_shield_target_otm_pct':       ParamRule(float, 0.1,   10.0,  'Base target % OTM for retreat strike'),
'atm_shield_loss_split_aggressor': ParamRule(float, 0.0,   1.0,   'Fraction of loss recovered from endangered-side re-sell'),
'atm_shield_max_per_session':      ParamRule(int,   1,     10,    'Max shield fires per side per session'),
'atm_shield_cooldown_mins':        ParamRule(int,   0,     60,    'Min minutes between shield fires on same side'),
```

### 16.7 mmm_activity.py

Add to ACTIVITY_TYPES dict:
```python
'atm_shield': 'ATM Shield',
```

### 16.8 mmm_websocket.py

```python
def emit_atm_shield(sid: str, data: dict):
    """Emit ATM Shield fire event to connected clients."""
    from .mmm_ws_emitter import safe_emit
    safe_emit('atm_shield', {'session_id': sid, **data})
```

Data structure:
```json
{
  "session_id": "...",
  "side": "ce",
  "endangered_strike": 73000,
  "spot_price": 72640,
  "distance_pct": 0.50,
  "fire_number": 1,
  "fires_remaining": 2,
  "new_strike": 73500,
  "effective_target_otm_pct": 1.0,
  "realized_loss": 0.60,
  "lots_closed": 10,
  "lots_sold_endangered": 2,
  "lots_sold_safe": 5,
  "sympathetic_shifted": true,
  "timestamp": "2026-03-12T..."
}
```

### 16.9 mmm_strike_shift.py — find_new_strike()

Add `min_otm_distance: float = 0.0` parameter:

```python
def find_new_strike(
    initializer,
    session: Dict,
    side: str,
    spot_price: float,
    min_otm_distance: float = 0.0,   # NEW: minimum absolute distance from spot
) -> Tuple[Optional[float], float]:
```

Filter chain candidates:
```python
# Existing filter: strike must be OTM
# NEW filter: if min_otm_distance > 0, strike must also be beyond min distance
if min_otm_distance > 0:
    if side == 'ce' and strike < spot_price + min_otm_distance:
        continue
    if side == 'pe' and strike > spot_price - min_otm_distance:
        continue
```

### 16.10 MMMSettingsDialog.js — ATM Shield Section

Add a new settings accordion section for ATM Shield:

```
🛡️ ATM Shield
  ├── Master Switch (toggle, default OFF)
  ├── Proximity % (slider 0.1–5.0, step 0.1, default 0.5)
  ├── Target OTM % (slider 0.1–5.0, step 0.1, default 1.0)
  ├── Loss Split Aggressor (slider 0.0–1.0, step 0.05, default 0.3)
  ├── Max Fires Per Session (number 1–10, default 3)
  └── Cooldown Minutes (number 0–60, default 10)
```

Add a "Recommended" chip next to the toggle. Tooltip text: "ATM Shield pre-empts positions going ATM by closing and retreating to a safer OTM strike. Fires when active strike is within proximity_pct of spot."

---

## 17. Edge Cases

| Scenario | Behavior |
|---|---|
| **No viable OTM strike found at target distance** | Close only (loss absorbed). Log warning. Sympathetic rebalance still runs. |
| **Both CE and PE simultaneously endangered** | Skip shield this beat. Let close_at_ATM handle. Log: "both sides ATM — deferring to close_at_ATM." |
| **Partial close failure** (some positions in-flight) | `_being_closed` flag prevents duplicate orders. Unclosed positions retried next beat. Shield sets cooldown; properly closed positions are reflected in state. |
| **Safe side has no active strike** | Skip safe-side recovery sell. 100% of recovery goes to endangered side. |
| **Close succeeds but re-sell fails** (exchange error) | Dangerous side goes to 0 active lots. One-side-close guard will detect → PAUSE. This is the correct safety behavior; don't try to auto-recover from exchange errors. |
| **Shield fires during wind-down** | Close executes (risk reduction + accelerates wind-down). Re-sell skipped. Sympathetic shift skipped. |
| **Proactive shift already ran on same side** | `_proactive_shifted_{side}` flag is set → skip shield for that side this beat. Proactive shift already handled the repositioning. |
| **Shield fires on CE, but close_at_ATM also triggered** | Deferral logic (Section 12) prevents close_at_ATM from running if shield has capacity. |
| **total_realized_loss <= 0** (buyback was cheaper) | `max(loss, 0)` = 0 → recovery_lots = 0. But `base_lots` (original position) are STILL re-sold at new strike. Shield fires for repositioning even when no loss. Position correctly shifted with same lot count. |
| **First fire at 30min to expiry (time_mult=3.0)** | effective_target_otm = 1.0% × 3.0 × 1.0 = 3.0%. Premium at 3% OTM may be very low (< shift_threshold). Falls back to farthest viable strike with premium ≥ shift_threshold. If none exists, close-only. |
| **max_per_session = 1** (conservative user config) | Only one fire allowed. After that, all reverts. close_at_ATM back as primary protection. |
| **Cooldown still active (fired 5 min ago, cooldown=10)** | Skip shield. Position sits closer to ATM. Triggers may fire and generate a normal adjustment. Or close_at_ATM fires if spot keeps moving. |

---

## 18. Why This Becomes Profitable

With ATM Shield, the premium collection landscape changes:

| Market Condition | Frequency | Without Shield | With Shield |
|---|---|---|---|
| Normal (±0.3% daily) | ~60% of days | Full premium both sides | Same — shield never fires |
| Mild trend (0.5-1.5%) | ~30% of days | T1/T2: 30% lot reduction + partial blocking | **Full premium both sides, no blocking** |
| Strong trend (1.5-3%) | ~8% of days | T3: all sells blocked after ~$5 CE spike | CE blocked (shield retreat happens), PE sells at boost |
| Extreme (3%+) | ~2% of days | T4: wind-down | Shield exhausts, reverts to wind-down |

**The real alpha is in the 30% of "mild trend" days.** Currently, a 0.7% BTC move triggers T1 → 30% lot reduction on both sides for the rest of the session. That's 30% less premium on every remaining heartbeat. On a 0.7% trend day, shield never fires (CE at 1.4% OTM is still 0.7% from spot — not within proximity threshold). But Trend Guard is still misfiring defensively. Shield simply turns that off.

**On strong trend days**, the value equation:
- 1 shield fire costs: ~0.5% of notional on closed position (typical slippage + spread)
- 1 shield fire earns: PE keeps selling at full capacity for the rest of the session
- Net on typical strong trend day: ~2-3 CE retreat losses, offset by 4-6 hours of unblocked PE premium

**Bounded downside:** After max fires, the position is at 2-6% OTM (depending on time/trend intensity). Wind-down handles the graceful exit. Max loss is still bounded by `max_loss_amount` + trailing stop.

---

## 19. Open Questions / Corrections Needed

Mark any items below as ✅ (approved), ❌ (rejected — explain), or ✏️ (modify — explain):

**Design decisions:**

- [ ] 19.1 `atm_shield_enabled` defaults to `False` in DEFAULT_PARAMS — changed to `True` in WebUI per your preference, but code default is `False` for safety. **Agree?**

- [ ] 19.2 Shield checks `active_strike`, not `original_strike`. After each fire, active_strike moves farther away. **Confirm this is the right strike to watch.**

- [ ] 19.3 T1/T2 + Shield ON → `ACTION_NORMAL` (no lot reduction, no blocking). Safe-side trend boost still works independently. **Agree with this behavior?**

- [ ] 19.4 T3/T4 + Shield ON → `BLOCK_CE_SELLS` (uptrend) or `BLOCK_PE_SELLS` (downtrend) — dangerous side blocked, safe side free. **Agree?**

- [ ] 19.5 Shield RE-SELL on endangered side is exempt from directional regime blocks (otherwise session PAUSES from one-side-close). **Agree with this exemption?**

- [ ] 19.6 Sympathetic rebalance uses `_process_strike_shift()` on the safe side (freeze + sell at new strike). This reuses the existing battle-tested function. **Agree, or prefer close + sell directly?**

- [ ] 19.7 `find_new_strike()` gets a `min_otm_distance` parameter added. No other behavior changes. **Agree?**

- [ ] 19.8 Loss split: 30% from endangered side re-sell, 70% from safe side re-sell. **Adjust these defaults?**

- [ ] 19.9 Progressive widening: each successive fire on the same side = base OTM × (1 + count × 0.5). So 1st=1.0x, 2nd=1.5x, 3rd=2.0x. **Adjust the step size (0.5)?**

- [ ] 19.10 After shield exhaustion, **all** original behavior resumes including wind-down trigger at T4. **Should there be a transition period or is immediate revert OK?**

**Implementation:**

- [ ] 19.11 `mmm_atm_shield.py` as a new file vs adding to `mmm_strike_shift.py`. **Prefer new file for separation of concerns?**

- [ ] 19.12 WebUI: ATM Shield section in MMMSettingsDialog with 6 controls. Show fire count in session status panel? **Want a visual indicator of how many fires remain per side?**

- [ ] 19.13 Telegram alert when shield fires? (similar to other critical events). **Yes/No?**

- [ ] 19.14 Should shield fire count reset when a new round starts (both sides closed and new positions opened)? **Yes (fresh session = fresh shield capacity)?**

---

## Changelog

| Version | Date | Change |
|---|---|---|
| v1 | Mar 12, 2026 | Initial plan (overcomplicated, had "freeze" similar to existing shift) |
| v2 | Mar 12, 2026 | Corrected per user: close + retreat, not freeze |
| v3 | Mar 12, 2026 | Added dynamic time scaling, progressive widening, sympathetic rebalance |
| v4 | Mar 12, 2026 | Added regime override, close_at_ATM deferral, shield re-sell exemption |
| v5 | Mar 12, 2026 | Final: T1/T2=NORMAL, T3/T4=BLOCK_CE/PE_only, full interaction matrix, per-file details |
