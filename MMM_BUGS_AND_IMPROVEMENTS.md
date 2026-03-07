# MMM Algo — Bug Fixes & Profitability Improvement Plan
## Based on: Session `mmm26feb26-1` Deep Analysis
## Date: February 25, 2026

---

> This document is a **decision brief** — not a coding spec. Every item has been verified against the live activity log and actual source code. Read this before touching any parameter or code.

---

## PART A: CONFIRMED BUGS (Fix These First)




**The deeper insight:**
A short strangle's adjustment logic should not treat each move as "I lost X, let me collect X." That's a martingale approach. Better framing: "I need to rebalance my delta and collect some time premium — but each rebalance should be capped at a fraction of initial position size." Think of it as rebalancing, not loss recovery.

---

### IMPROVEMENT-2 🔴 CRITICAL — Enable Trend Guard From Session Start, With Correct Parameters

**What happened:**
The trend guard eventually blocked CE sells at 15:01 UTC (3 hours into the session). By then, CE had gone from $107 to $724. The trend guard protected nothing — it came too late.

**Why it was late:**
The `trend_move_pct` threshold was 1.5%. BTC needed to move 1.5% from the session anchor before the trend guard activated. With BTC at ~$65,100 at entry, a 1.5% move = $976.50. But the session started monitoring after the fact, and the EMA slope confirmation added further delay. By the time the trend was "confirmed," the algo had already done 13 adjustments.

**The better approach — tiered trend response:**
| BTC Move from Anchor | Action |
|------|------|
| +0.5% | Log alert: "BTC trending, reduce hedge lot size by 30%" |
| +1.0% | Block CE sells (don't add more short calls into a rally) |
| +1.5% | Block ALL new option sells (no PE or CE) — protect existing |
| +2.0% | Activate wind-down mode: start buying back the most exposed side |

The current config has only one threshold (1.5%) with one action (block CE sells). Adding gradations means the algo starts responding earlier with smaller corrections rather than a binary full-block late in the game.

**Also critical:** The trend anchor should be the **session entry BTC price** (which it appears to be), but it should also check the **rate of acceleration** — a $500 BTC move in 10 minutes is very different from a $500 move in 3 hours. The current EMA slope check is a good start but needs to be more sensitive.

---

### IMPROVEMENT-3 🔴 HIGH — Asymmetry Hard Block, Not Just Warning

**What happened:**
CE stayed at 132 lots while PE grew to 700 lots (5.3:1 ratio). The asymmetry check fires at 3:1 (warning, continue) and 5:1 (alert, warn). Neither level **blocks** new adjustments. By the time 5:1 was reached, the damage was done.

**The improvement:**
Add a third asymmetry level — a **hard block**:
| Ratio | Level | Action |
|-------|-------|--------|
| 3:1 | Warning | Continue, log |
| 5:1 | Alert | Warn, reduce lot size for next adj by 50% |
| 7:1 | **Hard Stop** | **Block all new sells on the larger side** |

When PE is 7× CE lots, selling more PE doesn't hedge CE — it creates a new, independent risk. The algo should be forced to either buy back some PE or raise the CE cap (with explicit user confirmation) before proceeding.

**Additional rule:** When asymmetry exceeds 5:1, the max lot size for any single adjustment should be halved automatically. This slows the accumulation even if blocking is not triggered.

---

### IMPROVEMENT-4 🔴 HIGH — Strike Shift Lot Reduction (Higher Strike = More Risk Per Lot)

**What happened:**
When PE shifted from 63200 to 64400, the algo sold 34 lots at 64400 @ $149.50. When it shifted to 65400, it sold 88 lots @ $141. The lot calculation formula doesn't account for the fact that a closer-to-ATM strike carries **significantly higher gamma and delta per lot**.

**The problem:**
At 63200 PE (BTC ~$66k), delta per lot ≈ 0.10. Premium per lot: ~$80.
At 64400 PE (BTC ~$66k), delta per lot ≈ 0.20. Premium per lot: ~$149.
At 65400 PE (BTC ~$67k), delta per lot ≈ 0.35. Premium per lot: ~$141.

The formula uses hedge_premium in the denominator, so it sells fewer lots when premium is higher — this is partially correct. But it doesn't scale by delta. Selling 88 lots of 65400 PE at delta 0.35 means the portfolio's PE-side delta = 88 × 0.35 = 30.8 BTC delta exposure. If BTC falls $1,000, PE losses = $30,800 from delta alone, before gamma kicks in.

**The improvement:**
When a strike shift occurs, automatically apply a **lot reduction multiplier** based on the proximity to ATM:
- New strike OTM by >3%: no reduction (same formula)
- New strike OTM by 2–3%: multiply calculated lots by 0.75
- New strike OTM by 1–2%: multiply by 0.50
- New strike OTM by <1%: multiply by 0.25 (near ATM — be very conservative)

This ensures the algo doesn't blindly max out lot sizes on high-gamma near-ATM strikes.

---

### IMPROVEMENT-5 🟡 HIGH — Wind-Down Mode Should Be The Default After 3 Same-Direction Adjustments

**What happened:**
The algo did CE aggressor adjustments 7 times in a row (Adj #3, #4, #6, #7, #8, #9, #10, #11 — interrupted only by small reversals). Each added more PE lots. By the time the position cap was raised, the algo was deep in a losing hedging spiral.

**The insight:**
Three or more consecutive same-direction adjustments is a **trend signal**, not noise. If CE keeps rising for 3 consecutive adjustments, the market is trending up. At that point, the optimal response is NOT to add more PE — it's to:
1. Stop adding to PE (you've already collected enough PE premium)
2. Optionally buy back some cheap PE (they're falling in value anyway)
3. Consider CE position reduction

**The improvement — "Trend Cooldown Mode":**
After 3 consecutive same-direction adjustments, automatically switch from "standard" lot formula to a capped mode:
- Max lots for any single adjustment = 25% of initial_lots (25 lots for a 100-lot session)
- This collects some premium but doesn't compound the asymmetry
- After the 5th consecutive same-direction adjustment, require a manual approval via force heartbeat before any new sells in that direction

This is distinct from the existing whipsaw detection (which looks for alternating patterns). This new protection catches **runs** — sustained one-directional moves.

---

### IMPROVEMENT-6 🟡 HIGH — Max Loss Should Scale With Position Size

**What happened:**
The `max_loss_amount` default is $5,000. But by adj #11, the position was 132 CE + 700 PE lots. The 50% pnl_guardrail warning fired at 15:00 — meaning losses approached $2,500.

**The problem:**
$5,000 max loss for a 832-lot position (initial × 8.32) is completely inadequate as a hard stop. The position's natural mark-to-market fluctuation on any given day can easily exceed $5,000 due to spread alone.

**The improvement:**
`max_loss_amount` should be suggested (and validated) as a function of position size:
```
suggested_max_loss = initial_lots × target_premium_per_lot × 0.50
```
For this session: 100 lots × $207 total premium × 0.50 = **$10,350** suggested minimum.

Additionally, the max_loss calculation should **not** include unrealized PnL from positions that are OTM and decaying normally. The current implementation counts all unrealized losses equally — but a PE that was sold at $85 and is now worth $5 has "lost" $80 on the books but will expire worthless and be $85 profit at expiry. Counting that as a loss triggers the guardrail incorrectly.

**Better max-loss calculation:**
- Count **CE unrealized loss** (CE options going against you = real risk)
- Do NOT count PE unrealized gain as offsetting (it will realize at expiry)
- Count perp realized losses
- This gives a more accurate picture of actual risk vs. accounting P&L

---

### IMPROVEMENT-7 🟡 HIGH — Implement "CE Buyback" Action in Safety Response

**What happened:**
When the PE cap was hit (13:54), adjustments were blocked. The algo could only watch CE rise from $418 to $724 with no defensive action except tiny perp hedges. The perp hedge is not sufficient to offset 132 lots of short CE going deeply ITM.

**The missing capability:**
The algo has no ability to buy back options. It only sells. When CE becomes severely ITM/high-premium, the safest action is to **buy back some CE lots** — reducing the tail risk at the cost of realized loss, rather than letting it compound to settlement.

**The improvement:**
Add a **CE buyback trigger** that activates when:
1. CE premium exceeds 3× the entry price (e.g., entry at $107.50 → trigger at $322.50)
2. Position cap on PE is already at 80%+ utilization
3. CE is within 1% of becoming ITM (strike - spot < 1% of spot)

At this point, buy back `min(20, ce_lots)` CE lots. This is not a full position close — it's a surgical reduction of the most dangerous exposure. The premium buyback cost is a controlled, known loss vs. the uncontrolled, unlimited settlement loss.

This is a fundamental capability gap — the algo has no buyback tool at all.

---

### IMPROVEMENT-8 🟡 MEDIUM — Session Entry Regime Pre-Check

**What happened:**
The session entered at 12:02 UTC. BTC at ~$65,100. CE strike 67000 = 2.9% OTM. PE strike 63200 = 2.9% OTM. Within 5 minutes of entry, the market was already moving strongly toward CE (adj #1 fired at 12:07 — only 5 minutes after start).

**The insight:**
A session that triggers its first adjustment within 5 minutes of entry is a session that entered into a moving market. The ideal entry for a short strangle is into a range-bound, low-momentum market. An entry regime check would have flagged this.

**Pre-entry checks to add:**
1. **Momentum check**: Is the 5-minute RV (realized volatility over last 5 minutes of BTC price) above threshold? If BTC moved more than 0.5% in the 10 minutes before entry, delay entry.
2. **IV rank check**: Is current IV higher than the 30-day average? High IV = better premium collection but also more dangerous market.
3. **Time-of-day check**: Entering within 1 hour of a major macro event (options expiry, CPI, Fed meeting) should require confirmation.
4. **Strangle width check**: Should CE and PE strikes be equidistant from spot? Today's session had CE at 67000 (2.9% OTM) and PE at 63200 (2.9% OTM) — equal. Good. But if the market has directional bias, the strikes should be asymmetric (wider CE if market is bullish).

---

### IMPROVEMENT-9 🟡 MEDIUM — Perp Hedge Should Increase Size When Options Are Capped

**What happened:**
When PE hit the 500-lot cap, the perp hedge was the only remaining risk management tool. But it was managing tiny delta changes (0.02 BTC swings). With 132 short CE lots and BTC rising, the negative CE delta was growing significantly, but the perp was only hedging the incremental changes.

**The improvement:**
When the options position cap is hit AND CE is still moving against the position, the perp hedge should switch from "incremental delta rebalancing" mode to "full portfolio delta hedge" mode:
- Calculate total portfolio delta across ALL positions (CE + PE at all strikes + perp)
- Target: net delta = 0.0
- Execute a single, properly-sized perp trade rather than many small ones
- Maintain this full hedge until a manual reset or session close

This would have, in today's session, resulted in a significantly larger perp long position (matching the full negative delta of 132 short CE lots at high delta levels), providing meaningful protection during the cap period.

---

### IMPROVEMENT-10 🟡 MEDIUM — Hot-Reload Cap Raise Should Require Risk Acknowledgment

**What happened:**
The user raised `max_lots_per_side` three times (300→500, 500→700, 700→1000) during the session. Each raise was a desperate attempt to allow more PE hedging as CE kept rising. But each raise deepened the structural asymmetry without fixing the CE exposure problem.

**The improvement:**
When a hot-reload increases `max_lots_per_side`, the system should automatically calculate and display:
```
⚠️ Cap raise impact:
  Current CE unrealized loss: ~$XX,XXX
  New max PE lots allowed: XXX
  If next adjustment fully utilizes new capacity: PE total = XXX lots
  CE/PE asymmetry after cap raise: X.X:1
  Note: Raising PE cap does not reduce CE exposure.
  Confirm? [YES / CANCEL]
```

This is a one-time calculation at the moment of hot-reload, before the change is applied. It gives the operator a reality check: "You are about to allow more PE selling, but CE is already at X× entry. Is that what you want?"

---

### IMPROVEMENT-11 🟢 MEDIUM — Position Rebalancing: Allow PE Buyback When Asymmetry >5:1

**The gap:**
The algo can only sell options. It cannot buy back PE lots to rebalance the book when PE becomes excessively large relative to CE. This is a fundamental one-sidedness.

**The improvement:**
When PE/CE asymmetry exceeds a configurable threshold (e.g., 6:1), add a "rebalance PE" option:
- Buy back the cheapest PE lots (lowest strike, most OTM) in batches
- This returns collected premium to the market but reduces the position's exposure to a sharp BTC reversal
- Each buyback lot eliminates an existing liability and reduces margin requirement

Parameters needed: `rebalance_enabled`, `rebalance_asymmetry_threshold`, `rebalance_lots_per_trigger`

---

### IMPROVEMENT-12 🟢 MEDIUM — Session Auto-Pause at "Both Sides Up" Should Notify, Not Just Log

**What happened:**
At 15:03:34, both CE ($724.71) and PE ($133.41) were simultaneously above their trigger levels. The system logged this and paused for manual intervention. But "logging and pausing" is silent — if the operator isn't watching the activity feed, they won't know until they check.

**The improvement:**
"Both sides up" should trigger an immediate **push notification** (Telegram, SMS, or at minimum a loud UI alert) regardless of whether the WebUI is open. This is the most dangerous state the algo can enter, and it requires human judgment in minutes, not hours. The existing Telegram module in `mmm_telegram.py` should be specifically called for this event with a critical-level message.

---

### IMPROVEMENT-13 🟢 LOW — Whipsaw Cooldown Should Distinguish "Market Reversal" From "Algo Oscillation"

**Current behavior:**
Three alternating adjustments trigger a 600-second pause regardless of why they alternated. If the market genuinely oscillated (BTC went up, then down, then up in 20 minutes), the whipsaw was appropriate. But if the alternation was caused by incorrect trigger snapshots (like the ghost trigger scenario), the pause is punishing the algo for a software bug.

**The improvement:**
Before pausing for whipsaw, check if the alternating triggers were actually valid:
- Each triggered premium must be at least `min_trigger_move%` above the snapshot at the time of trigger
- If any alternating trigger was "stale" (triggered on a snapshot that was 0 or very old), it doesn't count toward the whipsaw limit
- This prevents a software bug from triggering a 10-minute safety pause in a legitimate market

---

## PART C: PARAMETER RECOMMENDATIONS FOR FUTURE SESSIONS

Based on this session's behavior, the following parameter configuration would significantly improve risk management:

| Parameter | Current/Default | Recommended | Reason |
|-----------|----------------|-------------|--------|
| `min_trigger_move` | 3.0% | **5.0%** | 3% fires too often in volatile crypto — adds too many positions in trending markets |
| `whipsaw_limit` | 3 | **3** | Keep — it correctly triggered today |
| `trend_enabled` | True | True | Keep but lower `trend_move_pct` |
| `trend_move_pct` | 1.5% | **1.0%** | Catch trends earlier, block sooner |
| `trend_action` | block_sells | **wind_down** | After detecting trend, start reducing positions rather than just blocking new ones |
| `max_lots_per_side` | 300 | **150–200** | Start conservative; raise manually only after confirming market is range-bound |
| `wind_down_enabled` | False | **True** | Always enable wind-down as a backstop |
| `wind_down_hours_before_expiry` | — | **4.0** | Start winding down 4 hours before expiry |
| `wind_down_on_atm` | False | **True** | Activate wind-down automatically if any strike becomes ATM |
| `perp_hedge_rebalance_band` | 0.005 | **0.015** | Reduce perp flip frequency significantly |
| `perp_hedge_max_flips_per_hour` | 6 | **4** | Further limit perp direction changes |
| `adjustment_interval` | ~240s | **300s** | Slower heartbeat reduces trigger frequency in volatile markets |
| `close_at_threshold` | 5.0 | **10.0** | Close PE lots earlier (at $10 instead of $5) — frees up margin faster |
| `max_loss_amount` | ~$5,000 | **$20,000+** | Calibrate to actual position size (see Improvement-6) |
| `itm_guard_enabled` | True | **True** | Critical — never sell ITM options near expiry |
| `cooldown_on_reversal` | True | **True** | Keep |
| `adaptive_interval_enabled` | True | **True** | Keep |
| `premium_buffer_pct` | 5% | **3%** | Slightly reduce — 5% adds lots that increase cap utilization faster |

---

## PART D: THE SINGLE MOST PROFITABLE CHANGE

If you implement only one thing from this document, implement this:

### Add a "Max Same-Direction Adjustment" Limiter

The algo's profitability depends on collecting premium from both sides over time. The single biggest threat to profitability is **running out of capacity on one side while the market trends**. Once PE hits the cap, the algo is naked on CE with no hedge capacity. That's where all the unrealized loss comes from.

**The rule**: After 3 consecutive same-direction adjustments, the maximum lots for the next adjustment in that same direction = **min(calculated_lots, initial_lots × 0.25)**. After 5 consecutive same-direction adjustments, require a **force heartbeat manual confirmation** before proceeding.

This single rule would have:
- Limited Adj#3 from 71 lots to 25 lots (100 × 0.25)
- Limited Adj#4 from 54 lots to 25 lots
- Slowed PE accumulation dramatically
- Preserved hedge capacity for longer
- Resulted in a smaller but more sustainable position by the time the cap was reached

The premium collected would be slightly less per session, but the tail risk would be dramatically reduced. **Lower risk per session × more successful sessions = better long-term profitability** than one big collection followed by a potential wipeout.

---

## SUMMARY TABLE

| ID | Category | Severity | Type | Est. Complexity |
|----|----------|----------|------|-----------------|
| BUG-1 | Missing adj_complete after strike shift | 🔴 Critical | Bug | Medium |
| BUG-2 | Ghost trigger — no abort event | 🔴 Critical | Bug | Low |
| BUG-3 | Force heartbeat bypasses whipsaw | 🟡 High | Bug | Low |
| BUG-4 | Strike shift not logged | 🟡 High | Bug | Low |
| BUG-5 | Perp flip frequency too high | 🟡 Medium | Bug/Config | Low |
| BUG-6 | Cap alert doesn't escalate | 🟡 Medium | Observability | Low |
| BUG-7 | PE fill latency in fast market | 🟢 Low | Design | Low |
| IMP-1 | Lot sizing compounding formula | 🔴 Critical | Design | High |
| IMP-2 | Trend guard too late, too blunt | 🔴 Critical | Design | Medium |
| IMP-3 | Asymmetry hard block missing | 🔴 High | Design | Low |
| IMP-4 | Strike shift lot reduction | 🔴 High | Design | Medium |
| IMP-5 | Consecutive same-direction limiter | 🟡 High | Design | Medium |
| IMP-6 | Max loss scaling with position | 🟡 High | Config/Design | Low |
| IMP-7 | CE buyback capability | 🟡 High | New Feature | High |
| IMP-8 | Pre-entry regime check | 🟡 Medium | New Feature | Medium |
| IMP-9 | Full-delta perp when capped | 🟡 Medium | Design | Medium |
| IMP-10 | Cap raise risk acknowledgment | 🟡 Medium | UI/UX | Low |
| IMP-11 | PE rebalancing (buyback) | 🟢 Medium | New Feature | High |
| IMP-12 | Both-sides-up notification | 🟢 Medium | Feature | Low |
| IMP-13 | Smarter whipsaw detection | 🟢 Low | Design | Medium |

---

*This document was generated from live session analysis. All bugs were verified against actual log events and source code. All improvements are based on observed failure modes, not hypothetical scenarios.*

*Next step: Prioritize BUG-1 through BUG-4 for immediate fixes (zero risk of unintended consequences — purely observability). Then IMP-1 and IMP-5 for profitability (require careful parameter calibration and testing).*
