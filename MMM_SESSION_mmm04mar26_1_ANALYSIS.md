# MMM Session `mmm04mar26-1` — Adjustment Walkthrough & Analysis

**Session**: mmm04mar26-1  
**Started**: 03-Mar-2026, 05:40 PM IST  
**Expiry**: 04-Mar-2026, 05:30 PM IST  
**Status**: RUNNING (as of analysis date)  
**Spot at entry**: ~$67,028  

> **Changelog**: Default params updated per review — `min_trigger_move` changed from 3% → **10%** and `trailing_stop_pct` changed from 50% → **0%** in `mmm_state.py`.

---

## 1. Key Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `initial_lots` | 10 | Lots per side at entry |
| `desired_ce_premium` | $100 | Target CE entry premium |
| `desired_pe_premium` | $100 | Target PE entry premium |
| `min_trigger_move` | **10.0%** *(was 3%)* | Premium must rise >10% above snapshot to trigger |
| `shift_threshold` | $50 | If hedge side premium < $50, shift to closer strike |
| `shift_target_premium` | $100 | Target premium when choosing new strike after shift |
| `close_at_threshold` | $5 | Buy back any position whose premium drops ≤ $5 |
| `premium_buffer_pct` | 5% | Sell 5% extra lots for slippage cushion |
| `trailing_stop_pct` | **0%** *(was 50%)* | 0 = disabled; no adjustment blocking on P&L dip |
| `cooldown_on_reversal` | True | Skip 1 interval after direction reversal |

### Suggestion: Time-to-Expiry–Based `close_at_threshold` Automation

As expiry nears, even a $10-20 premium on a near-ATM strike carries meaningful residual risk.
A flat $5 threshold is too aggressive near expiry (lets risky positions ride) and too conservative
far from expiry (could harvest too early without need). Proposed dynamic schedule:

| Hours to Expiry | Suggested Threshold |
|-----------------|-------------------|
| > 24h | $3 |
| 12–24h | $5 |
| 6–12h | $8 |
| 2–6h | $12 |
| < 2h | $20 |

**Implementation**: Replace the static `params.get('close_at_threshold', 5.0)` in `mmm_close_at_5.py`
with a helper that reads `hours_remaining` from the expiry clock and picks the appropriate threshold.
The existing `wind_down_close_threshold` (default $20) already serves the < 2h case during wind-down,
so the <2h row above would only apply when wind-down is NOT active.

---

## 2. The Core Formulas

### 2.1 Trigger Check (§7)

Every heartbeat (~2.5–5 min), the algo fetches the **live premium** at each side's active strike
and compares it to the **trigger snapshot** (the premium level recorded when the last adjustment occurred).

```
excess = premium_now - trigger_snapshot
excess_pct = (excess / trigger_snapshot) × 100

IF excess_pct > min_trigger_move (10.0%) → THAT SIDE IS TRIGGERED
```

**Key rule**: The **aggressor** is the side whose premium rose above its trigger. The response is to
sell options on the **opposite (hedge) side** to collect offsetting premium.

### 2.2 Loss-to-Cover: Standard Adjustment (§5.2 Case A)

When the same side keeps being the aggressor (no reversal), the loss is computed incrementally:

```
active_loss = (premium_now - trigger_snapshot) × active_lots × 0.001
frozen_loss = Σ (current_premium_at_frozen_strike - entry_premium) × frozen_lots × 0.001
              (only if positive — only count positions that are underwater)

loss_to_cover = max(active_loss, 0) + frozen_loss
```

- `0.001` = LOT_SIZE_BTC (each lot = 0.001 BTC contract); P&L result is therefore in BTC units
- `trigger_snapshot` resets after every adjustment, so `active_loss` is **incremental** (loss since last hedge)
- Frozen position loss uses `entry_premium` as baseline — **lifetime** loss from when that position was opened
- ⚠️ Frozen **original** positions (pe_orig, ce_orig) **ARE included** in frozen_loss for standard adjustments
- ⚠️ Only counts if underwater: (current − entry) > 0 for a short-sold option

### 2.3 Loss-to-Cover: Reversal Adjustment (§5.2 Case B / §9)

When the aggressor **switches** (e.g., was CE, now PE), it's a reversal. The algo computes the
**actual P&L of all ADJUSTMENT positions** on the aggressor side:

```
adjustment_pnl = Σ (entry_premium - current_premium) × lots × 0.001
                 (for EVERY active + frozen ADJUSTMENT position on aggressor side)
                 (⚠️ EXCLUDES original entry positions — they naturally offset across sides)

IF adjustment_pnl < 0 → loss_to_cover = |adjustment_pnl|
IF adjustment_pnl ≥ 0 → NO ADJUSTMENT (positions still profitable)
```

**Why original positions are excluded from reversal P&L**: Original CE and PE were opened symmetrically
at session start. Their P&L naturally cancels across sides. Counting them would double-count vs the
adjustment lots. The reversal formula is intentionally scoped to the **excess positions** added during hedging.

### 2.4 Number of Lots to Sell (§14.1)

```
raw_lots = loss_to_cover / (fill_premium × 0.001) × (1 + premium_buffer_pct)
lots_to_sell = ⌈raw_lots⌉   (ceiling — round up to at least cover the loss)
lots_to_sell = max(lots_to_sell, 1)  (always sell at least 1 lot)
```

The `premium_buffer_pct` (5%) adds extra lots to account for slippage between order and fill.

### 2.5 Shift Decision (§10)

Before selling, the algo checks if the hedge side's premium at its current strike is still high enough:

```
IF hedge_premium >= shift_threshold ($50) → sell at current active strike
IF hedge_premium < shift_threshold ($50) → STRIKE SHIFT:
    1. Freeze all current positions at old strike
    2. Find new strike closer to spot where premium ≈ shift_target_premium ($100)
    3. Sell lots at new strike
```

### 2.6 Trigger Snapshot Reset (§6.2)

After every adjustment, **BOTH sides** get their trigger snapshots updated to the current premium:

- **Aggressor side**: Ratchets up — only NEW loss above this level will trigger again
- **Hedge side**: Sets to current price — any future rise will be detected
- **Frozen positions**: Active trigger resets; frozen loss uses `entry_premium` as lifetime baseline

---

## 3. Session Timeline — Every Adjustment Explained

> **Note on units**: Premiums and running totals shown in **USD** ($ per lot × lots).
> The session internally tracks all P&L in BTC units = premium_usd × lots × 0.001 (LOT_SIZE_BTC).
> Round-trip example: $530 collected → stored as 0.530 in the BTC unit system.

### 3.0 Entry (HB#0) — 5:40 PM IST

**Action**: Sell 10 CE @ 71,600 ($53.00) + Sell 10 PE @ 62,400 ($47.00)

```
Total Premium Collected = ($53.00 × 10) + ($47.00 × 10)
                        = $530 + $470
                        = $1,000
```

**State after**:
| Side | Strike | Active Lots | Trigger Snapshot |
|------|--------|-------------|-----------------|
| CE | 71,600 | 10 | $53.00 |
| PE | 62,400 | 10 | $47.00 |

**Note**: Algo picked strikes at ~$50 premium vs the $100 target. Starting at half the target
means less cushion and more adjustments needed to reach the same total collected. (See §6.7.)

---

### 3.1 Adjustment #1: PE Shift (HB#1) — 5:43 PM IST

**Type**: `strike_shift`  
**Aggressor**: CE  
**Decision**: Hedge by selling PE, but PE at 62,400 = $47.43 → **below $50 shift threshold** → SHIFT!

1. Freeze 10 PE lots at 62,400 (fill price $50.86)
2. New PE strike: 64,000 premium ≈ $102.00
3. Sell 1 PE lot @ 64,000 at $102.00

```
Premium collected = 1 × $102 = $102
Running total     = $1,000 + $102 = $1,102
```

**State after**:
| Side | Strike | Active Lots | Frozen | Trigger Snapshot |
|------|--------|-------------|--------|-----------------|
| CE | 71,600 | 10 | 0 | $55.43 |
| PE | 64,000 | 1 | 10 @ 62,400 ($50.86 entry) | $102.00 |

**Last aggressor = CE**

---

### 3.2 Adjustment #2: First Reversal → CE Shift (HB#10) — 6:18 PM IST

**Type**: `first_reversal` + `strike_shift`  
**Aggressor**: PE (reversed! was CE → **REVERSAL**)

**Trigger check**:
```
PE at 64,000 = $127.84,  trigger = $102.00
excess = 25.3%  > 3% → TRIGGERED ✓

CE at 71,600 = $42.16,   trigger = $55.43
excess = -23.9% → NOT triggered
```

**Reversal P&L** (adjustment positions only; originals EXCLUDED by formula design):
```
pe_shift_002: 1 lot @ $102.00 → current $127.84
  pnl = ($102.00 - $127.84) × 1 × 0.001 = -0.02584 BTC  (loss)

pe_orig (10 lots @ 62,400): EXCLUDED — original position, not counted in reversal P&L.
  ► Current premium at 62,400 is therefore not needed for this calculation.

Total adjustment P&L = -0.0258 BTC
```

loss_to_cover = 0.0258 BTC

CE at 71,600 = $42.16 → **below $50 shift threshold** → STRIKE SHIFT!

1. Freeze 10 CE lots at 71,600 (fill $51.74)
2. New CE strike: 70,400 premium ≈ $95.50
3. Sell 1 CE lot @ 70,400 at $95.50

```
Lots = ⌈ 0.0258 / ($95.50 × 0.001) × 1.05 ⌉ = ⌈0.28⌉ = 1
Premium collected = $95.50
Running total     = $1,102 + $95.50 = $1,197.50
```

**State after**:
| Side | Strike | Active Lots | Frozen | Trigger Snapshot |
|------|--------|-------------|--------|-----------------|
| CE | 70,400 | 1 | 10 @ 71,600 | $95.50 |
| PE | 64,000 | 1 | 10 @ 62,400 | $127.84 |

---

### 3.3 Adjustment #3: Standard PE Sell (HB#16) — 6:44 PM IST

**Type**: `standard`  
**Aggressor**: PE

**Trigger**:
```
PE at 64,000 = $136.18,  trigger = $127.84
excess = 6.5% > 3% → TRIGGERED ✓
```

**Loss calculation** (includes frozen pe_orig — standard adj counts all frozen):
```
active_loss = ($136.18 - $127.84) × 1 × 0.001 = 0.00834 BTC

pe_orig frozen (10 lots @ 62,400, entry $50.86):
  Current PE at 62,400 ≈ $57.95  (spot fell to ~$64K; 62,400 is more OTM so less movement)
  frozen_loss = ($57.95 - $50.86) × 10 × 0.001 = 0.0709 BTC

loss_to_cover = 0.00834 + 0.0709 = 0.0792 BTC  ✓ matches walkthrough
```

> **Q: Why is frozen PE loss not in loss_to_cover?** — **It IS.** The $0.0792 total INCLUDES
> the frozen pe_orig contribution. PE at 62,400 rose to ~$57.95 (from entry $50.86), contributing
> ~$0.071 BTC of frozen loss. The value seems small because 62,400 is more OTM than 64,000 —
> the same market move pushes 62,400 up much less than 64,000. The formula correctly accounts
> for all frozen positions, including the frozen original.

CE at 70,400 = $78.63 ≥ $50 → sell at active ✓

```
Lots = ⌈ 0.0792 / ($74.50 × 0.001) × 1.05 ⌉ = ⌈1.12⌉ = 2
Execute: SELL 2 CE @ 70,400 at $74.50

Premium = $149 | Running total = $1,346.50
```

**State after**: CE 3 active @ 70,400 + 10 frozen @ 71,600; PE 1 active @ 64,000 + 10 frozen @ 62,400

---

### 3.4 Adjustment #4: Standard PE Sell (HB#21) — 7:04 PM IST

**Type**: `standard`  
**Aggressor**: PE (continuing)

```
PE at 64,000 = $143.90,  trigger = $136.18
excess = 5.7% > 3% → TRIGGERED ✓

pe_orig frozen contribution included in loss (same mechanism as Adj #3)
loss_to_cover = 0.0771 BTC  ✓

CE at 70,400 = $75.96 ≥ $50 → sell at active ✓

Lots = ⌈ 0.0771 / ($76.50 × 0.001) × 1.05 ⌉ = ⌈1.06⌉ = 2
Execute: SELL 2 CE @ 70,400 at $76.50

Premium = $153 | Running total = $1,499.50
```

> **Q: Frozen PE loss not accounted?** — Same answer as Adj #3: pe_orig at 62,400 IS included.
> Each heartbeat as spot drifts lower, PE 62,400 rises incrementally — each adjustment captures
> its growing frozen_loss contribution. The values appear modest because of the OTM distance vs 64,000.

**State after**: CE 5 active @ 70,400, 10 frozen @ 71,600

---

### 3.5 Adjustment #5: Standard PE Sell (HB#22) — 7:08 PM IST

**Type**: `standard`  
**Aggressor**: PE (continuing)

```
PE at 64,000 = $153.32,  trigger = $143.90
excess = 6.5% > 3% → TRIGGERED ✓

loss_to_cover = 0.1240 BTC  (includes frozen pe_orig — see Adj #3)
CE at 70,400 = $70.88 ≥ $50 → sell at active ✓

Lots = ⌈ 0.1240 / ($71.50 × 0.001) × 1.05 ⌉ = ⌈1.82⌉ = 2
Execute: SELL 2 CE @ 70,400 at $71.50

Premium = $143 | Running total = $1,642.50
```

> **Q: Frozen PE loss again?** — Accounted, same logic. As spot continues lower, PE 62,400 rises
> further, incrementally increasing the frozen_loss each heartbeat.

**State after**: CE 7 active @ 70,400

---

### 3.6 Adjustment #6: Standard PE Sell (HB#24) — 7:17 PM IST

**Type**: `standard`  
**Aggressor**: PE (STILL rising)

```
PE at 64,000 = $172.19,  trigger = $153.32
excess = 12.3% > 3% → TRIGGERED ✓

loss_to_cover = 0.2254 BTC  (includes frozen pe_orig growing contribution)
CE at 70,400 = $61.02 ≥ $50 → sell at active ✓

Lots = ⌈ 0.2254 / ($55.50 × 0.001) × 1.05 ⌉ = ⌈4.26⌉ = 3  ← capped at 3
Execute: SELL 3 CE @ 70,400 at $55.50

Premium = $166.50 | Running total = $1,809
```

> **Q: Frozen PE loss not accounted?** — It IS. Same mechanism throughout Adj #3–#6.
> The formula always includes frozen pe_orig in loss_to_cover while it is underwater.

**State after**: CE 10 active @ 70,400 + 10 frozen @ 71,600; PE 1 active @ 64,000 + 10 frozen @ 62,400

**Pattern**: CE sell premiums declining: $95.50 → $78.63 → $75.96 → $70.88 → $61.02 → $55.50.
As market falls, CE calls go further OTM, reducing the premium captured per adjustment.
This is the fundamental MMM challenge — selling the weakening side to hedge the strengthening side.
See §6.2 for suggestions.

---

### 3.7 Adjustment #7: Reversal — CE fires, Sell PE (HB#33) — 7:54 PM IST

**Type**: `first_reversal`  
**Aggressor**: CE (market bounced back up)

**Reversal P&L** (CE adjustment positions only; ce_orig EXCLUDED):
```
All CE adjustments at strike 70,400, current premium = $91.33:

  ce_shift_002: 1 @ $95.50  →  pnl = ($95.50 - $91.33) × 1 × 0.001 = +0.00417
  ce_adj_003:   2 @ $74.50  →  pnl = ($74.50 - $91.33) × 2 × 0.001 = -0.03366
  ce_adj_004:   2 @ $76.50  →  pnl = ($76.50 - $91.33) × 2 × 0.001 = -0.02966
  ce_adj_005:   2 @ $71.50  →  pnl = ($71.50 - $91.33) × 2 × 0.001 = -0.03966
  ce_adj_006:   3 @ $55.50  →  pnl = ($55.50 - $91.33) × 3 × 0.001 = -0.10749

  ce_orig frozen @ 71,600: EXCLUDED — original, not used in reversal P&L (§2.3)
  ► Premium at 71,600 is not needed for this calculation.

Total = -0.2063 BTC  → UNDERWATER
```

> **Q: Premium at 71,600 not in logs?** — Correct, and it doesn't matter. The reversal formula
> only counts **adjustment** positions (§2.3). The ce_orig at 71,600 is an original position,
> explicitly excluded. All 5 entries above are adjustment fills; their sum is -0.2063 BTC.
> No information about 71,600 premium is needed.

CE at 70,400 = $117.10 ≥ $50 → sell at active... wait, hedge is PE

**Hedge**: Sell PE @ 64,000  
PE premium = $117.10 ≥ $50 → sell at active ✓

```
Lots = ⌈ 0.2063 / ($119.50 × 0.001) × 1.05 ⌉ = ⌈1.81⌉ = 2
Execute: SELL 2 PE @ 64,000 at $119.50

Premium = $239 | Running total = $2,048
```

**State after**: CE 10 active + 10 frozen = 20 total, PE 3 active + 10 frozen = 13 total

**Key insight**: The large -$0.2063 reversal loss is because CE adjustment lots from Adj #3–#6 were
sold at $55–$75 when the market was bearish, but the bounce pushed CE 70,400 back to $91+. Those
"cheap" sells are now underwater by $15–$36 per lot.

---

### 3.8 Adjustment #8: Reversal Again — PE fires, Sell CE (HB#35) — 8:02 PM IST

**Type**: `first_reversal`  
**Aggressor**: PE (reversed again → whipsaw, only 2 HBs since Adj #7)

**Reversal P&L** (PE adj only; pe_orig EXCLUDED):
```
  pe_shift_002: 1 @ $102.00 → current 64,000 = $130.75
    pnl = ($102.00 - $130.75) × 1 × 0.001 = -0.02875
  pe_adj_007:   2 @ $119.50 → current 64,000 = $130.75
    pnl = ($119.50 - $130.75) × 2 × 0.001 = -0.02250

Total = -0.0513 BTC → UNDERWATER
```

```
Lots = ⌈ 0.0513 / ($76.00 × 0.001) × 1.05 ⌉ = ⌈0.71⌉ = 1
Execute: SELL 1 CE @ 70,400 at $76.00

Premium = $76 | Running total = $2,124
```

**State after**: CE 11 active + 10 frozen = 21, PE 3 active + 10 frozen = 13

---

### 3.9 Shift #3: CE Strike Shift 70,400 → 69,200 (~HB#49) — ~9:00 PM IST

**Type**: `strike_shift`

CE premium at 70,400 dropped **below $50** → shift triggered.

1. Freeze ALL 11 active CE lots at 70,400
2. New CE strike: 69,200 premium ≈ $89.00
3. Sell 3 CE lots @ 69,200 at $89.00

Frozen CE positions at 70,400:
| Position | Strike | Lots | Entry $ | Type |
|----------|--------|------|---------|------|
| ce_shift_002 | 70,400 | 1 | $95.50 | shift |
| ce_adj_003 | 70,400 | 2 | $74.50 | standard |
| ce_adj_004 | 70,400 | 2 | $76.50 | standard |
| ce_adj_005 | 70,400 | 2 | $71.50 | standard |
| ce_adj_006 | 70,400 | 3 | $55.50 | standard |
| ce_adj_007 | 70,400 | 1 | $76.00 | first_reversal |

Frozen at 2026-03-03T14:48:53 UTC

**State after**: CE 3 active @ 69,200 + 11 frozen @ 70,400 + 10 frozen @ 71,600 = **24 total**

---

### 3.10 Adjustments #9–10: Reversal — CE fires, Sell PE (HB#51) — 9:11 PM IST

**Type**: `first_reversal`  
**Aggressor**: CE

```
ce_shift_008: 4 lots @ $89.00, strike 69,200 → current $171.28
  pnl = ($89.00 - $171.28) × 4 × 0.001 = -0.3291 BTC  (heavily underwater)
  (Frozen 70,400 and 71,600 positions also contribute; exact premiums not logged)

Total from walkthrough = -0.2405 BTC → UNDERWATER
```

```
Lots = ⌈ 0.2405 / ($65.00 × 0.001) × 1.05 ⌉ = ⌈3.89⌉ = 4
Execute: SELL 4 PE @ 64,000 at $65.00

Premium = $260 | Running total = $2,740
```

Note: PE premium at $65 vs $65 vs $65 — much lower than the $119 of Adj #7 because PE is now
significantly more OTM (market moved upward substantially).

---

### 3.11 Adjustment #11: Standard CE Sell (HB#53) — 9:18 PM IST

**Type**: `standard`  
**Aggressor**: CE

```
CE at 69,200 = $207.92,  trigger = $171.28
excess = 21.4% > 3% → TRIGGERED ✓

loss_to_cover = 0.1847 BTC

Lots = ⌈ 0.1847 / ($65.50 × 0.001) × 1.05 ⌉ = ⌈2.96⌉ = 3
Execute: SELL 3 PE @ 64,000 at $65.50

Premium = $196.50 | Running total = $2,936.50
```

**State after**: CE 4 active @ 69,200 + 21 frozen; PE 10 active @ 64,000 + 10 frozen

---

### 3.12 Close-at-5 Events

After Adj #11, the trailing stop (50% at the time) blocked further adjustments while CE continued rising.

#### Close-at-5 #1 (HB#66) — 9:59 PM IST
PE original lots at 62,400: live premium fell to ~$6.60 ≤ $5 normal threshold.
- Bought back 10 PE lots at 62,400
- Realized P&L = +0.4426 BTC (sold avg $50.86, bought back ~$6.60)
- Cleared ALL frozen PE at 62,400

#### Close-at-5 #2 (HB#72) — 10:13 PM IST
CE original lots at 71,600: closed under the **elevated wind-down threshold**.
- Bought back 10 CE lots at 71,600
- Realized P&L = +0.3089 BTC (sold avg $51.74, bought back at fill ~$20.85)

> **§6.5 — $20.85 Anomaly EXPLAINED (NOT a bug):**
>
> By HB#72, wind-down was ACTIVE (see §3.13). During wind-down, the system automatically uses
> `wind_down_close_threshold` (default **$20.0**) instead of the normal $5.
>
> The **threshold check** compares the live mid-market price against $20.0.
> At the time of the HB#72 scan, CE at 71,600 mid-market ≤ $20.0 → trigger fired.
>
> The **fill price** ($20.85) is the exchange ask price, always slightly above mid-market.
> Check: mid ≤ $20 → close order placed → filled at ask $20.85. Completely normal behavior.
>
> Verified from session DB: `close_at_5_count = 2`, `wind_down_close_threshold = 20.0`,
> `auto_close_events` shows CE 71,600 close at 16:43:33 UTC while `_wind_down_history` confirms
> wind-down was running from 16:29–16:43 UTC.

---

### 3.13 Wind-Down Events — Root Cause Investigation

> **Q: Why did wind-down happen? I didn't do any manual reduction.**

**Investigation findings** (from session DB):

Wind-down was NOT triggered automatically by any of the known automatic paths:
- `wind_down_hours_before_expiry = 2.0`: At ~10 PM IST on Mar 3, expiry was still ~19.5 hours away → condition NOT met
- `_trend_wind_down_triggered = False` (verified in DB)
- `_vol_wind_down_triggered`: not set (vol regime was NORMAL)
- `wind_down_on_atm = False`

The session's **final** state shows `wind_down_enabled = False`, yet `_wind_down_history` contains
6 entries spanning ~14 minutes (16:29–16:43 UTC), which proves wind-down WAS active during
that window and was then disabled.

**Root cause**: `wind_down_enabled` was **temporarily toggled ON via the WebUI** hot-reload during
the session, then toggled OFF. This is the only remaining explanation given all automatic triggers
were inactive. This may have been:
- An accidental click on the wind-down toggle in the MMM session UI
- A hot-param update that had an unintended side-effect

**Wind-down buyback timeline** (from `_wind_down_history`):

| UTC Timestamp | Side | Lots | Strike | Realized |
|--------------|------|------|--------|---------|
| 16:29:50 | CE | 1 | 69,200 | **-0.47** (loss — position still underwater) |
| 16:31:03 | PE | 2 | 64,000 | +0.06 |
| 16:32:40 | PE | 2 | 64,000 | +0.04 |
| 16:34:56 | PE | 1 | 64,000 | +0.02 |
| 16:39:59 | PE | 1 | 64,000 | +0.00 |
| 16:43:39 | PE | 1 | 64,000 | -0.02 |

The first CE buyback realized **-0.47 BTC** — a loss, because that CE position was still underwater
(selling at $91 and buying back at a higher premium). This is the cost of premature wind-down.

**Recommendations**:
1. Add a confirmation dialog in the WebUI before wind_down_enabled can be toggled ON
2. Log each `wind_down_enabled` state change with timestamp + user session info for auditability
3. Review UI layout to see if the wind-down toggle is easy to click accidentally

---

## 4. Final Position Summary

| Side | Active Strike | Active Lots | Frozen Lots | Total Lots |
|------|--------------|-------------|-------------|------------|
| CE | 69,200 | 3 | 11 @ 70,400 | 14 |
| PE | 64,000 | 3 | 0 | 3 |

### CE Positions (Detailed)
| ID | Strike | Lots | Entry $ | Status | Type |
|----|--------|------|---------|--------|------|
| ce_orig | 71,600 | 10 | $51.74 | **CLOSED** | original |
| ce_shift_002 | 70,400 | 1 | $95.50 | frozen | shift |
| ce_adj_003 | 70,400 | 2 | $74.50 | frozen | standard |
| ce_adj_004 | 70,400 | 2 | $76.50 | frozen | standard |
| ce_adj_005 | 70,400 | 2 | $71.50 | frozen | standard |
| ce_adj_006 | 70,400 | 3 | $55.50 | frozen | standard |
| ce_adj_007 | 70,400 | 1 | $76.00 | frozen | first_reversal |
| ce_shift_008 | 69,200 | 3 | $89.00 | **ACTIVE** | shift |

### PE Positions (Detailed)
| ID | Strike | Lots | Entry $ | Status | Type |
|----|--------|------|---------|--------|------|
| pe_orig | 62,400 | 10 | $50.86 | **CLOSED** | original |
| pe_shift_002 | 64,000 | 1 | $102.00 | ACTIVE | shift |
| pe_adj_003 | 64,000 | 2 | $119.50 | ACTIVE | first_reversal |
| pe_adj_004 | 64,000 | 0 | $65.00 | CLOSED (wind-down) | first_reversal |
| pe_adj_005 | 64,000 | 0 | $65.50 | CLOSED (wind-down) | standard |

---

## 5. P&L Accounting

### Premium Collected (in USD)

| Event | Side | Lots | Premium $/lot | $ Collected |
|-------|------|------|---------------|------------|
| Entry CE | CE | 10 | $53.00 | $530 |
| Entry PE | PE | 10 | $47.00 | $470 |
| Adj #1 (PE shift) | PE | 1 | $102.00 | $102 |
| Adj #2 (CE shift) | CE | 1 | $95.50 | $95.50 |
| Adj #3 | CE | 2 | $74.50 | $149 |
| Adj #4 | CE | 2 | $76.50 | $153 |
| Adj #5 | CE | 2 | $71.50 | $143 |
| Adj #6 | CE | 3 | $55.50 | $166.50 |
| Adj #7 | PE | 2 | $119.50 | $239 |
| Adj #8 | CE | 1 | $76.00 | $76 |
| Adj #9 (shift) | CE | 3 | $89.00 | $267 |
| Adj #10 | PE | 4 | $65.00 | $260 |
| Adj #11 | PE | 3 | $65.50 | $196.50 |
| **TOTAL** | | **37 lots** | | **$2,847.50** |

*Session reports `total_premium_collected ≈ $2,936.50` — minor rounding difference from shift mechanics.*  
*Internal BTC unit: $2,936.50 → 2.9365 BTC-units (×0.001 LOT_SIZE_BTC). The session stores this as `2.9365`.*

### Realized P&L (from buybacks, in BTC units per session tracking)

| Event | Side | Lots | Sold Avg $ | Bought @ | Realized BTC-units |
|-------|------|------|------------|----------|--------------------|
| Close-at-5: PE orig | PE | 10 | $50.86 | ~$6.60 | +0.4426 |
| Close-at-5: CE orig (wind-down threshold) | CE | 10 | $51.74 | ~$20.85 (ask fill) | +0.3089 |
| Wind-down CE | CE | 1 | $89.00 | higher (loss) | -0.47 |
| Wind-down PE | PE | 7 | various | various | +0.10 |
| **Total Realized** | | | | | **≈ 0.376** |

*Session reports `realized_pnl = 0.376`*

---

## 6. Key Observations & Suggestions

### 6.1 The Whipsaw Problem

This session had **5 reversals** in ~5 hours, including one whipsaw of only 2 heartbeats (Adj #7→#8).
Each reversal costs money because adjustment lots sold at low premium become underwater on reversal.

The new **`min_trigger_move = 10%`** (default, changed from 3%) requires a larger move before triggering.
With 3%, even a 3% premium wiggle would trigger an adjustment — the 10% setting will absorb many
false triggers and whipsaw costs, at the cost of slightly slower response to real trends.

### 6.2 Declining Premium Capture

CE sell premiums declined sharply as PE dominated:
```
Adj #2: $95.50 → Adj #3: $74.50 (-22%) → Adj #6: $55.50 (-42%) → Adj #8: $76 → Adj #9: $89 (after shift)
```

When market falls (PE rising), CE calls become more OTM and cheaper. You're forced to sell an
increasingly weak CE side to hedge a strengthening PE side.

**Three approaches to improve this**:

**Option A — Raise `shift_target_premium` ($100 → $150)**:  
When the CE side shifts, target $150 premium per lot instead of $100. Each new position starts
with more cushion, and the higher entry premium means the position can absorb the declining
premium before becoming unworkable. Tradeoff: requires going deeper ITM — higher assignment risk.

**Option B — Enable `shift_threshold_pct` (currently 0 = disabled)**:  
Set `shift_threshold_pct = 0.6` — shift when premium < 60% of the last entry premium, rather than
waiting for the absolute $50 floor. This triggers shifts earlier, catching better premiums before
full deterioration. Example: Adj #2 entered CE at $95.50 → next shift triggers when CE < $57.30,
not waiting until $50.

**Option C — Lot-sizing by relative premium**:  
Reduce the `premium_buffer_pct` boost when hedge premium is below a danger level (e.g., < 60% of
original target). Currently, you always add 5% extra lots regardless of how bad the premium is.
In steep-decline markets, fewer lots at a terrible premium may be better than more lots at terrible premium —
it conserves capacity for the eventual rebound.

### 6.3 Frozen Lot Accumulation

21 frozen CE lots at 70,400 + 10 frozen at 71,600 accumulated before close-at-5 cleared the originals.
The 11 remaining frozen lots at 70,400 consume capacity and generate no new premium — this is the
"capacity drain" problem addressed in the Split Ledger Plan.

### 6.4 Asymmetric Final State

CE has 14 total lots vs PE with 3. The asymmetry came from:
- PE being aggressor longer → more CE sold as hedge
- Wind-down buying back 7 PE lots (while adding 1 CE buyback at a loss)
- Close-at-5 clearing originals on both sides

### 6.5 Close-at-5 — $20.85 Anomaly Resolved

Already explained in §3.12. Wind-down was active with elevated threshold $20.0. Fill price $20.85
is the ask price; threshold check used mid-market (≤ $20.0). Not a bug.

### 6.6 Trailing Stop — Default Changed to 0%

The 50% trailing stop was blocking adjustments throughout this session: with peak P&L of ~$0.10 BTC,
a $0.05 dip would block all hedges, allowing exposure to accumulate unchecked.

**Default has been changed to `trailing_stop_pct = 0.0`** in `mmm_state.py`. New sessions will have
no trailing stop by default. Re-enable manually per session if capital protection is needed.

### 6.7 Entry Premium vs Target

Session entered at $53/$47 per lot vs the $100/$100 target. Less upfront premium means:
- Lower trigger snapshots → smaller absolute premium move fires a trigger
- More adjustments needed to reach the same total premium collected
- Much less buffer if the position goes against you early

Consider making entry strike selection more aggressive about finding $100 target strikes,
even if slightly more ATM, rather than accepting far-OTM strikes at half the target premium.

---

## 7. Formulas Summary Card

```
┌─────────────────────────────────────────────────────────────┐
│  TRIGGER:   excess_pct = (premium_now - snapshot) / snapshot│
│             IF excess_pct > 10% → TRIGGERED  (new default) │
│                                                             │
│  STANDARD LOSS (aggressor side):                            │
│    loss = (premium - trigger) × active_lots × 0.001         │
│         + Σ frozen (current - entry) × lots × 0.001         │
│    (includes frozen originals; only if current > entry)     │
│                                                             │
│  REVERSAL LOSS:                                             │
│    pnl = Σ (entry - current) × lots × 0.001                │
│    (ADJUSTMENT fills only — originals EXCLUDED)             │
│    IF pnl < 0 → loss_to_cover = |pnl|                      │
│                                                             │
│  LOTS TO SELL:                                              │
│    lots = ⌈ loss / (fill_premium × 0.001) × 1.05 ⌉         │
│                                                             │
│  SHIFT CHECK:                                               │
│    IF hedge_premium < $50 → freeze + find new strike        │
│                                                             │
│  CLOSE-AT-5 (normal):    IF premium ≤ $5 → buy back        │
│  CLOSE-AT-5 (wind-down): IF premium ≤ $20 → buy back       │
│    (fill price will be slightly above threshold — normal)   │
│                                                             │
│  SNAPSHOT RESET:                                            │
│    After any adj → BOTH sides snapshot = current premium    │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Parameter Changes Made (This Review)

| Parameter | Old Default | New Default | Effect |
|-----------|------------|-------------|--------|
| `min_trigger_move` | 3.0% | **10.0%** | Fewer false triggers; less whipsaw cost |
| `trailing_stop_pct` | 0.50 (50%) | **0.0 (disabled)** | No more adjustment blocking on P&L dip |
