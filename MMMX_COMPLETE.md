# MMMX — Monthly BTC Options Strategy (20–45 DTE)

> **Complete Implementation & Strategy Guide**
>
> **Status:** Final spec — v10.0 (all Q1–Q50 resolved + Third Safety Layer Hedging locked down)  
> **Last Updated:** 2026-04-05  
> **Total Lines:** ~3,200 lines across 27 backend files + 4 frontend components

---

## Quick Summary

MMMX is an **intelligent capital deployment system** for selling monthly BTC options (20–45 days to expiration). Unlike naive premium sellers that deploy all capital at entry and hope for stillness, MMMX:

- **Deploys in 10% tranches** — only when the market confirms opportunity (move + IV)
- **Protects via ATM Shield** — reposition any position before it approaches ATM
- **Hard stop is absolute** — scales dynamically with premium collected
- **Monitors dual-stream** — 1-hour heartbeat + real-time flash-crash detection
- **Positions survive directional moves** — old tranches go deeper OTM and collect theta

**Time horizon:** Weeks (not hours like MMM).  
**Capital model:** 100 lots budget + 30 lots ATM shield reserve.  
**Safety rule:** `close_at_dte >= 7` (hard-enforced — no exceptions).

---

# SECTION 1: STRATEGY PHILOSOPHY

## The Core Insight: Market as Negotiation

**Ordinary premium sellers** deploy all capital at entry. They pray the market stays within their comfort zone. When it doesn't, they panic and close everything.

**MMMX** treats the market like a negotiation:

1. **Enter small** — 10% of total budget  
2. **Listen carefully** — watch for market confirmation (move + IV)  
3. **Deploy more when confirmed** — commit more capital when the opportunity is clear  
4. **Never panic close** — reposition threatened positions (never leave them unhedged)  
5. **Hard stop is law** — absolute maximum loss, recalculated as premiums grow

## Core Objectives (Q26–Q28 — Formally Stated)

### Q26: What is the core objective of deployment?

**Theta capture through gradual capital commitment.**

The goal is to earn money from theta decay. Options expire worthless — that is the edge. The reason we deploy in tranches over 30–45 days (not all at once) is:
- We can never predict exact market direction over 30–45 days.
- By reserving capital, we always have money to adjust regardless of which direction the market moves.
- Deploying on confirmed moves (2% + IV) means we collect fat premiums at the right time, not blind entry at random prices.

**Primary objective: theta decay. Secondary: premium maximization at good entry points. Not delta directional betting.**

### Q27: What is the core objective of ATM Shield?

**Stay OTM. Never fight the market.**

MMMX operates like an insurance company. An insurance company does not wait for the house to catch fire and then refuse to pay — it raises premiums or revokes coverage in advance when it detects rising risk. When a position approaches ATM:
- The old "insurance" (short option) is becoming dangerous.
- We revoke it (buyback) and issue new insurance at a safer place (sell new OTM strike).
- The shield is not about recovering losses — it is about refusing to fight a trend. Stay OTM, collect smaller premium, avoid the real loss.

**Primary objective: survival (stay OTM). Secondary: loss recovery via recovery lots. Never profit maximization.**

### Q28: When deployment and protection conflict — who wins?

**Protection ALWAYS wins. No exceptions.**

Whenever any safety feature fires (hard stop, ATM Shield, delta gate, CB_NEAR_ITM, margin block):
- Deployment is suspended for that beat (or until the safety condition clears).
- There is no scenario where deploying capital is more important than protecting existing positions.

**Why:** Deploying a new tranche takes 30–45 days to earn theta. A bad loss from an unprotected position can wipe out weeks of gains in hours. Capital growth is slow; capital destruction is fast. Protection is always the priority.

```
Priority order (absolute, no overrides):
  1. Hard stop → close_all
  2. DTE close → close_all  
  3. ATM Shield → reposition
  4. Delta gates → reduce/roll
  5. CB circuit breakers → wake heartbeat / emergency reduce
  6. Deployment → deploy tranche (ONLY after all above pass)
```

### Q35: Operator Override Rules (Discipline Over Emotions)

**No manual override of hard stop. Period.**

MMMX is designed to protect you from yourself. When hard stop fires:

```
Operator tries: "Wait, don't close, market will recover"
System: CLOSES ALL IMMEDIATELY.
Telegram: "Hard stop hit. Session COMPLETE. No override possible."
Result: Capital preserved. Lessons learned.
```

**Why no override:**

- Hard stop is calculated based on portfolio risk math, not emotion
- If operator overrides → discipline breaks → losses compound
- The moment you let one loss "ride" for recovery → next loss hits → cascade failure
- Options decay fast; you can't afford to be wrong for long

**What the operator CAN do:**

1. **Adjust hard_stop_multiplier** (hot-reload) — before session starts, set your risk tolerance
2. **Adjust profit_booking_targets** — take partial profits when comfortable
3. **Pause deployment manually** — if you want to reduce new exposure
4. **Stop the session** — click STOP button to end session gracefully

But **once a session is running — hard stop is law. No exceptions.**

**The philosophy:**

Money management > timing > prediction. Hard stop enforces money management. Emotions enforce loss-making.

---

## The Asymmetry Principle (G28 — Non-Negotiable)

When BTC falls 6%, CE and PE behave DIFFERENTLY:

| Market Direction | Call (CE) | Put (PE) | Strategy |
|---|---|---|---|
| **Falls 6%** | Deep OTM → delta ↓ → premium decays → **profitable** | Toward ATM → delta ↑ → premium up → **threatened** | Roll CE forward (collect elevated IV), roll PE farther OTM (reduce delta) |
| **Rises 6%** | Toward ATM → delta ↑ → premium up → **threatened** | Deep OTM → delta ↓ → premium decays → **profitable** | Roll PE forward (collect elevated IV), roll CE farther OTM (reduce delta) |

**Key insight:** High IV after a move is an **OPPORTUNITY**, not a threat. The profitable side's premium decay is overwhelmed by IV spike — use this to deploy and collect fat premiums. The threatened side can be repositioned farther OTM to reduce exposure while still collecting (somewhat reduced) premium.

**This is what separates experienced traders from naive models.** Amateurs see directional move + high IV and close everything. Experts see high IV and redeploy.

---

# SECTION 2: CAPITAL STRUCTURE & DEPLOYMENT

## The Money Model

```
Per side (CE or PE):
├── TRANCHE BUDGET: 100 lots
│   ├── Tranche 1–10: 10 lots each
│   └── Deployed across days/weeks as market confirms
│
├── ATM SHIELD RESERVE: 30 lots
│   └── Used ONLY for protection recovery
│       (not for regular deployment)
│
└── TOTAL MAX EXPOSURE: 130 lots/side
```

**Why 30-lot reserve?**  
Historical data shows that in a sustained 6–8% move, a 5% OTM position will need repositioning 2–3 times. Each reposition needs recovery lots to offset the loss. 30 lots = 3 positions × ~10 lots recovery per position.

## Entry Gates (Operator Must Confirm)

Before Tranche 1 can deploy:

```
✓ Entry DTE:      20–45 days remaining (prevents final-week gamma)
✓ IV Rank:        >= 50th percentile (not selling vol lows)
✓ Margin:         < 80% utilized (room to reposition without margin call)
✓ Liquidity:      >= 5 lots bid depth, spread < 10% on both CE & PE strikes
```

**These are HARD GATES.** Session refuses to start if any fails.

## Tranche 1: Operator Manual Trigger

```
Step 1: Operator clicks "Scan Strikes" → System shows nearest strikes at otm_distance_pct
Step 2: Operator reviews premiums, deltas, bid depth
Step 3: Operator clicks "Deploy Tranche 1"
  → Sells 10 lots CE at CE_strike
  → Sells 10 lots PE at PE_strike
  → Session status: RUNNING
  → hard_stop_usd = 2.0 × premium_collected (initialized)
  → Monitor + Premium Listener threads start
```

## Tranches 2–10: Automatic, Heartbeat-Triggered

**Every 1 hour, the heartbeat evaluates deployment:**

### Deployment Trigger (OR Logic with Whipsaw Adjustment)

```
# Step 1: Calculate whipsaw-adjusted thresholds
if whipsaw_score >= 4:
  # COOLDOWN: Skip all deployments
  return NO_DEPLOYMENT
elif whipsaw_score == 3:
  # RESTRICT: Widen triggers 100% + halve lot size
  adjusted_move_pct = tranche_deploy_move_pct × 2.0  (2% → 4%)
  tranche_size = 5 lots (instead of 10)
elif whipsaw_score == 2:
  # CAUTION: Widen triggers 50%
  adjusted_move_pct = tranche_deploy_move_pct × 1.5  (2% → 3%)
  tranche_size = 10 lots
else:
  # NORMAL: Standard thresholds
  adjusted_move_pct = tranche_deploy_move_pct  (2%)
  tranche_size = 10 lots

# Step 2: Evaluate deployment trigger with adjusted thresholds
DEPLOY IF:
  (spot moved >= adjusted_move_pct from last deployment spot)
   OR
  (IV rank increased >= tranche_deploy_iv_delta since last deployment)
  AND tranches_remaining > 0
  AND margin < 80%
  AND ATM Shield did NOT fire this beat (shield has priority)
  AND whipsaw_score < 4 (COOLDOWN blocks all deployments)

Maximum: ONE tranche per beat, even if both conditions fire
```

**Default thresholds (hot-reloadable):**
- `tranche_deploy_move_pct` = 2% spot move (base threshold; widened by whipsaw score)
- `tranche_deploy_iv_delta` = 10 IV rank points
- Whipsaw adjustments: see [Whipsaw Guard](#whipsaw-guard-fourth-protection-layer--oscillation-control) section below

**Example with Whipsaw Adjustment:**

```
Base thresholds: move 2%, IV +10

Beat 0: Deploy Tr1, whipsaw_score = 0 (NORMAL)
        Threshold: 2% move → deploy Tr2 when spot moves 2%

Beat 1: Market oscillates, shield fires, whipsaw_score = 1
        Threshold: still 2% move (score 1 = NORMAL)

Beat 2: Another oscillation, whipsaw_score = 2 (CAUTION)
        Threshold: 3% move (2% × 1.5) → need 3% move for Tr3
        
Beat 3: Another shield fire, whipsaw_score = 3 (RESTRICT)
        Threshold: 4% move (2% × 2.0) → need 4% move for Tr3
        Tranche size: 5 lots (instead of 10)
        
Beat 4: Another oscillation, whipsaw_score = 4 (COOLDOWN)
        Deployment SKIPPED for next 1 hour
        Score will decay -2 at 1-hour mark, back to score 2 (CAUTION)
```

### Deployment Eligibility Queue (Capturing Large Moves)

**Problem Solved:** When BTC moves 6% in one heartbeat, only 1 tranche deploys (due to "one per beat" rule). This wastes the directional confirmation. 

**Solution:** Populate a queue of eligible tranches when a large move is detected. Deploy them one per beat over successive beats, but **clear the queue if market retraces** (move confirmation broken).

#### Queue Mechanics

```python
# When deployment trigger fires (Beat N):
spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100
num_eligible = floor(spot_move_pct / tranche_deploy_move_pct)

# Example: 6.4% / 2% = 3 tranches eligible
if num_eligible > 1:
    deployment_eligible_tranches = [Tr_next, Tr_next+1, ..., Tr_next+num_eligible-1]
    deployment_queue_triggered_spot = current_spot  # For retracement check
    deployment_queue_direction = 'UP' if current_spot > last_deployment_spot else 'DOWN'

# Deploy first from queue this beat
deploy_tranche(deployment_eligible_tranches.pop(0))

# Beat N+1: Check for DIRECTIONAL retracement (against the queue direction)
if deployment_queue_direction == 'UP':
    retracement = max(0.0, (deployment_queue_triggered_spot - current_spot) / deployment_queue_triggered_spot × 100)
else:  # DOWN queue
    retracement = max(0.0, (current_spot - deployment_queue_triggered_spot) / deployment_queue_triggered_spot × 100)

if retracement > 0.5:
    # Market retraced > 0.5% AGAINST the confirmed move
    deployment_eligible_tranches.clear()
    Telegram: "Queue cleared: {retracement}% retracement from trigger"
else:
    # Still valid, deploy next from queue
    deploy_tranche(deployment_eligible_tranches.pop(0))
```

#### Real Trading Example

```
Beat 0 (10:00 UTC, BTC $67,500):
  Manual Tranche 1 deployment
  last_deployment_spot = $67,500

Beat 1 (11:00 UTC, BTC $70,500):
  Move = (70,500 - 67,500) / 67,500 × 100 = 4.4%
  Eligible tranches = floor(4.4 / 2.0) = 2
  Queue: [Tr2, Tr3]
  deployment_queue_triggered_spot = $70,500
  
  Deploy Tr2 immediately
  Queue now: [Tr3]
  last_deployment_spot = $70,500
  Telegram: "4.4% move detected! Tr2 deployed. Queue: [Tr3]"

Beat 2 (12:00 UTC, BTC $71,500):
  Queue direction: UP
  Directional retracement: max(0, (70,500 - 71,500) / 70,500) = 0.0%
  0.0% > 0.5% threshold? NO, queue stays valid ✓
  
  Deploy Tr3 from queue
  Queue now: []
  last_deployment_spot = $71,500

Beat 3 (13:00 UTC, BTC $69,000):
  Queue direction: UP
  Directional retracement: (70,500 - 69,000) / 70,500 = 2.1%
  2.1% > 0.5% threshold? YES, retraced against move!
  Queue cleared (already empty, but if it had Tr4 it would be removed)
  
  ✗ NO deployment this beat
  Telegram: "Retracement detected (-2.1% from queue trigger). Pausing deployment."

Beat 4 (14:00 UTC, BTC $74,000):
  NEW move check from last deployment spot: (74,000 - 71,500) / 71,500 = 3.5%
  Eligible = floor(3.5 / 2.0) = 1
  Queue: [Tr4]
  deployment_queue_triggered_spot = $74,000
  
  Deploy Tr4 immediately
  Queue now: []
  Telegram: "2.1% new move detected. Tr4 deployed."
```

#### Session State Fields

Add to `session` dict:
```python
'deployment_eligible_tranches': [],        # Queue of pending tranche IDs
'deployment_queue_triggered_at': None,     # UTC timestamp when queue was populated
'deployment_queue_triggered_spot': None,   # Spot price that triggered queue (for retracement check)
'deployment_queue_direction': None,        # 'UP' or 'DOWN' direction of queued move
```

#### Benefits Over Single-Tranche-Per-Move

| Scenario | Without Queue | With Queue |
|---|---|---|
| 6.4% move | 1 tranche (Tr2 only) | 3 tranches (Tr2, Tr3, Tr4) across 3 beats |
| Move retraces at 50% | 1 tranche wasted | 2 tranches deployed, queue clears before waste |
| Multiple moves | Lost opportunity on each | Each move gets appropriate tranches |
| Capital preserved | ❌ Deployed at worst time | ✅ Retracement blocks excess deployment |

### Strike Selection (Live API Required)

**CRITICAL: Use live exchange API to find strikes. Do NOT hardcode step sizes.**

Delta Exchange's strike intervals vary by price level and DTE. Hardcoding is wrong.

```python
# 1. Compute raw target
raw_ce_target = current_spot × (1 + otm_distance_pct / 100)
raw_pe_target = current_spot × (1 - otm_distance_pct / 100)

# 2. Fetch live available strikes from Delta
available = delta_client.get_strikes(
    asset='BTC',
    expiry_date=session['expiry_ddmmyy'],
    contract_type='call_options' or 'put_options'
)
# caches at session start + refresh each beat

# 3. Snap to nearest on live ladder
ce_strike = min(available, key=lambda s: abs(s - raw_ce_target))
pe_strike = min(available, key=lambda s: abs(s - raw_pe_target))

# 4. Build symbol: C-BTC-{strike}-{DDMMYY} or P-BTC-{strike}-{DDMMYY}
```

**After deployment:**
```
last_deployment_spot = current_spot          # MANDATORY — next beat's move trigger uses this as reference
last_deployment_iv_rank = current_iv_rank    # MANDATORY — next beat's IV delta trigger uses this as reference
total_premium_collected += new_premium
hard_stop_usd = hard_stop_multiplier × total_premium_collected  # RECALCULATE
tranches_deployed += 1                       # deployment tranches only (type == 'deployment')
tranches_remaining -= 1                      # deployment tranches only
ce_reserve_remaining = ce_reserve_remaining  # NOT changed by regular deployment — shield reserve untouched
pe_reserve_remaining = pe_reserve_remaining  # NOT changed by regular deployment — shield reserve untouched
```

**Why `last_deployment_spot` and `last_deployment_iv_rank` are mandatory:**
Both are the reference baseline for the next deployment trigger check:
- `spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100`
- `iv_delta = current_iv_rank - last_deployment_iv_rank`

If ATM Shield fires and does NOT update these, the next deployment beat computes the move from the pre-shield spot — potentially over-triggering the queue with stale distance. **ATM Shield must update both fields after any reposition that changes the active strikes**, so the deployment distance is measured from the new position's spot reference, not the old one.

### Why 1 Hour (Not 24 Hours)?

Within 1 hour:
- **Retraces** → IV subsides → do NOT deploy (correct!)
- **Holds** → IV elevated → deploy at new ATM → collect fat premium (correct!)
- **Continues** → strong directional signal → deploy again (correct!)

A 24-hour cadence would miss the optimal deployment window. IV spikes decay after 2–4 hours. Missing that window wastes premium collection opportunities.

---

# SECTION 3: PROTECTION MECHANISMS

## Hard Stop (Absolute Session-Wide Ceiling)

```
hard_stop_usd = hard_stop_multiplier × total_premium_collected
Default multiplier: 2.0 (can be hot-reloaded, minimum 1.0)
```

**Evaluated FIRST at every heartbeat before all other logic:**

```
if total_pnl <= -hard_stop_usd:
  close_all_immediately()
  session_status = COMPLETE
  Telegram: CRITICAL
  return  # nothing else runs
```

**Example progression:**

| State | Premium Collected | Hard Stop |
|---|---|---|
| After Tranche 1 (10 lots) | $100 | -$200 |
| After Tranche 3 (30 lots) | $300 | -$600 |
| After Tranche 5 (50 lots) | $500 | -$1,000 |
| After Tranche 10 (100 lots) | $1,000 | -$2,000 |

**Hard stop scales dynamically.** As more tranches deploy, the hard stop grows with them. This is INTENTIONAL — larger position = larger acceptable loss in absolute dollars, but the multiplier keeps risk discipline.

**Hard stop during ATM Shield execution (Q21):** Hard stop is non-negotiable and always takes priority. Shield steps are treated as atomic to avoid creating naked states mid-operation.

If hard stop breaches while a shield step is in progress:
1. Set `hard_stop_pending = True` immediately.
2. Complete the current atomic step only (no mid-step interrupt).
3. At the next control boundary, run `close_all_immediately()` before any further trigger evaluation.
4. Session status → COMPLETE, Telegram: CRITICAL.

Hard stop is still evaluated at the **top of every heartbeat BEFORE shield runs**. If breach occurs between checks (e.g., during a reprice loop), it is forced at the next control boundary.

### Portfolio-Level Hard Stop (Q33 — Correlated Risk Protection)

**Hard stop is portfolio-level, not position-level.** It captures ALL positions (CE, PE, all tranches, all recovery lots) simultaneously.

```
total_pnl = SUM(tranche_pnl for all tranches) + SUM(recovery_tranche_pnl for all recovery lots)
hard_stop_usd = hard_stop_multiplier × total_premium_collected

if total_pnl <= -hard_stop_usd:
    close_all_immediately()  # ALL tranches + ALL recovery lots + ALL sides
```

**Why this prevents correlated risk (black swan):**

In a crash (e.g., BTC drops 15%):
- Both CE and PE deltas can spike unexpectedly
- Correlation between sides becomes highly positive
- Portfolio hedging assumptions break down
- Without hard stop: individual delta gates might trigger late, losses accumulate

**With portfolio hard stop:**
- No matter which side blows up first (CE or PE)
- No matter if correlation changes
- The moment portfolio P&L hits -hard_stop_usd → **EVERYTHING closes**
- **No partial hedges, no "let me wait for the rebalance," no correlation assumptions**

**Example:**

```
Tranche 1 (CE +PE): Entry at spot $67,500, premium = $100, hard_stop = $200
  - Over 24 hours: BTC crashes 15% to $57,375
  - CE: deep ITM (delta → 1.0), PE: deep OTM (delta → 0)
  - CE loss: -$1,000 (from 20Δ to close-to-ITM)
  - PE gain: +$50 (theta + vega decay)
  - Net portfolio P&L: -$950
  - Hard stop threshold: -$200
  - Result: **CLOSE ALL immediately** (no waiting for shield to reposition)
```

**Hard stop is non-negotiable and has absolute priority — it ALWAYS wins.**

### Hard Stop Execution Rule: Market on Danger, Limit on Safe Side

When `close_all_immediately()` fires, the execution strategy differentiates between **danger side** (losing positions) and **safe side** (hedges + any profitable positions):

```
For EACH tranche:
  - Danger Side (SHORT calls/puts):      BUY with MARKET order
    → Ensures immediate fill, stops the bleed
    → Accept market slippage (already losing money anyway)
  
  - Safe Side (LONG hedges):              SELL with LIMIT order
    → Target bid price for better execution
    → Hedges are insurance—no rush to liquidate
    → If limit doesn't fill, hedges expire worthless (acceptable)
```

**Example: BTC crashes 15%, hard stop fires**

```
Tranche 1:
  - Short 10 CE @ $70k strike:     BUY 10 CE (MARKET) → fill immediately at -$1,000
  - Short 10 PE @ $64k strike:     BUY 10 PE (MARKET) → fill immediately at +$50 (profit)
  - Long 10 hedge CE:               SELL 10 hedge CE (LIMIT at bid) → try to exit cleanly
  - Long 10 hedge PE:               SELL 10 hedge PE (LIMIT at bid) → try to exit cleanly

Outcome:
  - Shorts closed instantly, portfolio protection triggered
  - Hedges liquidate gracefully (limit fill, or expire worthless if market is thin)
  - Session COMPLETE, capital preserved
```

**Why this works:**
- **Market orders on shorts** = guarantee execution, stop losses immediately
- **Limit orders on hedges** = avoid panic selling, respect bid depth
- Hedges surviving (if limit doesn't fill) is acceptable — they're insurance, not capital recovery

---

### Gap Risk & Execution Reality (G36 — Acceptance of Slippage)

**Spec acknowledges: Hard stop trigger ≠ hard ceiling.**

When BTC gaps 10% instantly (e.g., flash crash, circuit breaker halt):

```
Reality sequence:
  1. Gap occurs: spot $65K → $58.5K (10% drop)
  2. PE deltas: 0.20 → 0.90 instantly
  3. CB_NEAR_ITM fires (delta ≥0.72) → immediate 50% PE reduce
  4. During reduction execution: market fills at gapped prices
  5. By time all reduces complete: actual P&L worse than hard stop trigger

Example:
  Hard stop trigger: -$200
  CB fires, reduces PE 50%
  Fills at gap prices (10% slippage)
  Actual loss when reduces complete: -$280 (breach by 40%)
```

**Design acceptance:**

- Hard stop is a **trigger point**, not a hard ceiling
- During fast moves, fills will slippage beyond the trigger
- System does NOT guarantee loss ≤ hard_stop_usd
- System GUARANTEES: when P&L hits hard_stop threshold → close_all fires immediately

**User expectation:** Accept 5–15% slippage overshoot during gaps. This is normal options market behavior.

**Why this is acceptable:**
- Without hard stop, loss is unlimited
- With hard stop, loss is bounded by market slippage + execution time
- Alternative (no hard stop) = potential total account wipeout
- This is the right trade-off

## Fees & P&L Calculation (Critical for Hard Stop & Accounting)

### Fee Structure

**Fees are read directly from the exchange fill response — never calculated independently.**

Delta Exchange returns the actual fee charged on every order fill. MMMX records that value verbatim, using the same method as the MMM algo (copy from `mmmx_executor` fill-processing). Do not reimplement fee math.

```python
# On every fill response from Delta Exchange:
actual_fee = fill_response['fee']          # actual USD fee charged by exchange
fees_tracking['total_fees_paid'] += actual_fee
fees_tracking['last_fee_charge'] = now_utc()

# For reference — Delta Exchange published rates (may change; exchange value is authoritative):
#   maker: 0.02%  |  taker: 0.05%
# These are stored in mmmx_constants.py for display only, NOT used in calculations.
```

**Fee accounting:**
- Recorded at **order fill**, not at order creation
- Source of truth: exchange fill response `fee` field (same as MMM algo)
- Deducted from realized P&L for closed positions
- Visible in audit log and dashboard under "Fees Paid"
- **NOT deducted from `total_premium_collected`** — premiums are gross, fees are separate
- **NOT used in hard stop calculation** — hard stop is based on gross premium, fee impact is secondary loss

### P&L Calculation (Realized + Unrealized)

**Per-position P&L:**

```
For SHORT position (sold premium):
  entry_premium = premium received at entry
  current_premium = current market price to buy back
  
  unrealized_pnl_gross = (entry_premium - current_premium) × lots × LOT_SIZE_BTC
  
  On close:
    exit_premium = premium paid to buy back
    realized_pnl_gross = (entry_premium - exit_premium) × lots × LOT_SIZE_BTC
    
For LONG hedge position (bought premium):
  entry_premium = premium paid at purchase
  current_premium = current market price to sell
  
  unrealized_pnl_gross = (current_premium - entry_premium) × lots × LOT_SIZE_BTC
  
  On close:
    exit_premium = premium received on sale
    realized_pnl_gross = (exit_premium - entry_premium) × lots × LOT_SIZE_BTC
```

**Portfolio-level P&L:**

```
total_pnl = SUM(unrealized_pnl_gross for open positions) 
          + SUM(realized_pnl_gross for closed positions)
          - total_fees_paid

This is what hard stop checks:
  if total_pnl <= -hard_stop_usd:
    close_all_immediately()
```

**Critical distinction:**
- `total_premium_collected` = gross premiums from SHORT positions ONLY (not including hedges)
- `total_pnl` = net P&L including unrealized + realized + all fees
- Hard stop multiplier is applied to GROSS premiums, but total_pnl includes fees
- Example: premium = $1,000, hard_stop = $2,000, but if fees are $100, actual max loss is $2,100

**Per-tranche P&L aggregation:**

```python
tranche_pnl_gross = (ce_unrealized_gross + pe_unrealized_gross + ce_realized_gross + pe_realized_gross)

portfolio_pnl = SUM(tranche_pnl_gross for all tranches)
              + SUM(recovery_tranche_pnl_gross for all recovery tranches)
              + SUM(hedge_pnl_gross for all hedges)
              - total_fees_paid  # Fees are deducted exactly once at portfolio level
```

**Recovery tranche P&L:**

Recovery tranches (2A, 2B, 2C) are calculated identically to regular tranches. Their P&L contributes to `total_pnl`. Fees on recovery lots are tracked separately but aggregated to portfolio total.

**Hedge P&L:**

```
hedge_pnl_gross = (current_premium - entry_premium) × lots × LOT_SIZE_BTC

Hedges are LONG positions (bought protection), so they have negative unrealized P&L while shorts are profitable, but positive unrealized P&L when shorts are threatened (market moved against shorts, so hedges gain value). Fees are applied once in `total_fees_paid` at portfolio level.

Example: BTC drops 6%
  Short PE @ 60K: unrealized loss = -$10,000
  Hedge PE @ 56K: unrealized gain = +$5,000
  Net P&L on this spread: -$5,000 + hedge_cost (-$85) = -$5,085
```

**Fee impact on hard stop:**

```
Scenario: 100 lots deployed, premium collected = $1,000, hard_stop = $2,000

Beat 1: Portfolio losing -$1,500, fees paid so far = $50
        total_pnl = -$1,500 - $50 = -$1,550
        Hard stop threshold = -$2,000
        Status: Still safe, but getting close

Beat 2: Portfolio losing -$1,800, fees paid so far = $120
        total_pnl = -$1,800 - $120 = -$1,920
        Hard stop threshold = -$2,000
        Status: Very close (within $80 of trigger)

Beat 3: Market gaps -2%
        Portfolio now = -$2,050, fees = $200
        total_pnl = -$2,050 - $200 = -$2,250
        Hard stop threshold = -$2,000
        BREACH: -$2,250 <= -$2,000 → CLOSE_ALL fired
```

**Why fees are separate from premium:**

Premiums are gross revenue. Fees are cost of doing business. Separating them allows:
- Accurate P&L calculation (premiums - costs = profit)
- Clear visibility on fee impact (how much of loss is slippage vs fees)
- Hard stop multiplier to be conservative (based on gross, actual max loss is gross + fees)
- Operator to understand true trading edge (premium after fees)

**Session-level fee tracking:**

```python
session['fees_tracking'] = {
    'total_maker_fees': 0.0,      # Fees paid when closing (if maker)
    'total_taker_fees': 0.0,      # Fees paid on entry/exit (taker)
    'fee_rate_maker': 0.0002,     # 0.02%
    'fee_rate_taker': 0.0005,     # 0.05%
    'total_fees_paid': 0.0,       # Sum of all fees
    'last_fee_charge': None,      # UTC timestamp of last fee
}

# Updated whenever an order fills
session['fees_tracking']['total_fees_paid'] += order_fee_amount
```

**Dashboard display:**

```
Portfolio P&L Section:
  Gross P&L (premiums only):     +$850
  Realized P&L (closed positions): +$120
  Unrealized P&L (open positions): +$50
  Fees Paid:                     -$42
  ─────────────────────────────
  NET P&L:                       +$978

  Hard Stop Threshold:           -$2,000
  Current Safe Margin:           +$2,978
```

---

## ATM Shield (Per-Position Protection)

**This is the secret sauce.** Every position is monitored independently. When any position's OTM buffer drops below 5%, the shield fires and repositions it — **never allowing a position to approach ATM**.

### Trigger

```python
for each position in each tranche:
  if side == 'ce':
    otm_remaining = (strike - spot) / spot × 100
  else:
    otm_remaining = (spot - strike) / spot × 100

  if otm_remaining < 5%:  # threshold is hot-reloadable
    SHIELD FIRES
```

### Execution Sequence (6 Steps)

**Step 1: Calculate loss**
```
buyback_premium = current market premium
entry_premium = position entry premium
loss = (buyback_premium - entry_premium) × lots × LOT_SIZE_BTC
```

**Step 2: Buy back endangered position**
- Set `_being_closed` guard (crash recovery)
- `smart_execute(buy, 10 reprice attempts × 30s each = 5 min max)`
- If fails: check if already closed on exchange (external close)
- If still open: fallback to `emergency_execute()` (IOC, aggressive)
- If STILL fails: **ABORT shield, do NOT proceed**

**Step 3: Sell new position at fresh strike**
- Recompute strike from CURRENT spot + OTM distance
- Use live API to find nearest available
- Sell original lot count at new strike using the **shield sell retry mechanism** (see below)

**Shield Sell Retry Mechanism (before pausing):**

Pausing is the last resort. Before pausing, the algo must exhaust the following retry sequence:

```
Attempt 1–10 (limit order reprice loop):
  1. Fetch live bid/ask for new strike
  2. Compute mid_price = (bid + ask) / 2
  3. Place SELL limit order at mid_price
  4. Wait 30 seconds for fill
  5. If filled → success, proceed to Step 4
  6. If not filled → cancel order
  7. Recompute mid_price from fresh bid/ask
  8. Repeat (up to 10 attempts)

Attempt 11 (market order fallback):
  9. Place SELL market order (IOC, no price limit)
  10. If filled → success, proceed to Step 4
  11. If STILL not filled → ABORT: session PAUSED + NAKED ALERT + Telegram CRITICAL
```

**Why 10 + 1 structure:**
- 10 × 30s = 5 minutes of patient limit-order tries at live mid-price — avoids market-impact slippage
- The 11th market order is the emergency floor — guarantees execution even in thin markets
- Only after ALL 11 attempts fail does the session pause, because a naked position (buyback done, no new sell) is the worst possible state

**If sell fails after all 11 attempts:** session PAUSED + NAKED ALERT + Telegram CRITICAL

**NAKED POSITION TIMEOUT (G37):**

If a position becomes naked (buyback succeeded, new sell failed):

```
1. Session paused immediately + Telegram CRITICAL alert
2. System enters "NAKED WATCH" mode
3. Every heartbeat (every 1 hour), check naked status:
   
   if time_naked > 30 minutes:
     → Force heartbeat now (don't wait 1 hour)
     → Try sell again using emergency_execute() (market order, IOC)
     → Send escalation Telegram: "Naked for 30min, emergency sell fired"
   
   if time_naked > 2 hours AND still naked:
     → Send operator Telegram CRITICAL alert
     → Recommendation: manual intervention required
```

**Why 30 min?**
- 30 min gap between emergency retries
- Gives market time to stabilize
- Prevents hammering exchange with repeated market orders
- But prevents sitting naked indefinitely

**Operator action:**
- If you see "Naked for 30min" alert → immediately login
- Check if position can be manually closed on exchange
- If market is broken → escalate to exchange support or accept the loss

**Step 4: Calculate recovery lots (30/70 split)**
```
ce_recovery_lots = ceil(loss × 0.30 / (new_ce_premium × LOT_SIZE))
pe_recovery_lots = ceil(loss × 0.70 / (new_pe_premium × LOT_SIZE))
```

**Why 30/70?** When one side is threatened, premium collection is skewed. The losing side needs more recovery lots to offset the loss. The winning side contributes 30% (it's still profitable).

**Step 5: Create recovery tranche (sibling naming)**

Recovery lots are NOT stored as a sublist on the parent tranche. They become a **new tranche in `session['tranches']`** with a sibling ID derived from the parent:

```
Parent tranche 2 → first recovery event → Tranche 2A
Parent tranche 2 → second recovery event → Tranche 2B
Parent tranche 2 → third recovery event → Tranche 2C  (max_shifts = 3)
```

Recovery tranche structure mirrors a regular tranche exactly:
```python
{
    'tranche_id': '2A',
    'parent_tranche_id': 2,
    'type': 'recovery',           # distinguishes from deployment tranches
    'shield_event': 1,            # which shield event on parent created this
    'deployed_at': '<utc_now>',
    'entry_spot': current_spot,
    'ce': {
        'lots': ce_recovery_lots,    # 30% of loss offset
        'strike': current_ce_strike,
        'entry_premium': ...,
        'entry_delta': ...,
        'shift_count': 0,            # own counter, independent of parent
        'status': 'ACTIVE',
        '_being_closed': False,
        '_being_closed_at': None,
    },
    'pe': {
        'lots': pe_recovery_lots,    # 70% of loss offset
        'strike': current_pe_strike,
        ...                          # same fields as ce
    },
    'premium_collected': ...,     # contributes to total_premium_collected
    'status': 'ACTIVE',
}
```

**Why sibling tranches, not sublists:**
- ATM Shield loop already iterates `for each tranche` — recovery tranches get full protection automatically, zero loop changes
- Hard stop, DTE close, delta gate, `close_all` — all tranche-level operations cover recovery tranches for free
- Recovery premiums contribute to `total_premium_collected` → hard stop scales correctly
- Analytics can trace causal chain: "Tranche 2 → Tranche 2A (recovery) → Tranche 2B (second recovery)"

**`tranches_deployed` and `tranches_remaining` are NOT updated when a recovery tranche is created** — these metrics track only the 10-tranche deployment budget. Gate: `type == 'deployment'` for deployment counters.

**Reserve accounting (CE and PE independent — 30 lots each):**
- CE reserve and PE reserve are tracked separately (`ce_reserve_remaining`, `pe_reserve_remaining`)
- Shield recovery deducts from each side independently: `ce_reserve_remaining -= ce_recovery_lots_used`; `pe_reserve_remaining -= pe_recovery_lots_used`
- If one side's reserve is exhausted: use available lots for that side only; other side unaffected
- If both reserves exhausted: reposition without recovery tranche, alert operator

**Step 6: Update state**
```
Close old position record on parent tranche
Add new position at new strike on parent tranche
Append recovery tranche (2A / 2B / 2C) to session['tranches']
Update CE reserve: ce_reserve_remaining -= ce_recovery_lots_used
Update PE reserve: pe_reserve_remaining -= pe_recovery_lots_used
Update total_premium_collected += recovery_tranche.premium_collected
Recalculate hard_stop_usd = hard_stop_multiplier × total_premium_collected
Update last_deployment_spot = current_spot         # MANDATORY — resets move reference after reposition
Update last_deployment_iv_rank = current_iv_rank   # MANDATORY — resets IV reference after reposition
tranches_deployed = tranches_deployed              # NOT changed — shield does not consume deployment budget
tranches_remaining = tranches_remaining            # NOT changed
Emit mmmx_shield_event
Telegram: "Shield fired: Tranche {id} {old_strike} → {new_strike}. Recovery: Tranche {recovery_id} created."
```

### Constraints

| Constraint | Rule |
|---|---|
| Max repositions per position | `atm_shield_max_shifts` = 3 (hot-reloadable) — maps to max 3 sibling recovery tranches per parent (2A, 2B, 2C) |
| No OTM strike available | **Hold new tranche deployment.** Every heartbeat, refresh live strike cache and recheck availability. Do NOT force-deploy into a missing strike. Already-open tranches: leave undisturbed if still sufficiently OTM. If any open tranche reaches `atm_protect_threshold`: apply full shield/delta-gate protection as normal (δ≥0.35 reduce, δ≥0.55 reduce-then-roll, δ≥0.70 hard-close). Telegram alert: "No OTM strikes available — deployment on hold." Retry silently each beat. |
| Max shifts exhausted | Apply delta-gate + Telegram tells operator to raise `atm_shield_max_shifts` |
| Reserve exhausted | Reposition without recovery, alert operator |
| Recovery tranche itself gets shielded | Treated identically to any regular tranche — full 6-step shield sequence applies; if reserve depleted, delta-gate is fallback |

### Multi-Shield Execution Order (G38 — Crisis Priority)

**When multiple tranches hit shield threshold in same beat:**

If shields_to_execute > 1:

```
1. Sort by priority:
   - Largest unrealized loss first (worst position goes first)
   - Tiebreaker: oldest tranche first (Tr1 before Tr2)

2. Pre-execute margin check:
   - Sum all required margin for all shields
   - If total_required > (total_margin - 10% buffer):
     → Execute shields sequentially
     → After each shield, recalculate remaining margin
     → If margin would breach: ABORT remaining shields
     → Close worst position only, let others be handled next beat

3. Execute shields in priority order:
   - Shield 1 (worst loss): full 6-step execution
   - Check margin after each step
   - Shield 2 (next worst): start only if margin OK
   - ... continue

4. Telegram: "3 shields fired (priority: Tr1 → Tr3 → Tr2). Margin: 45%"
```

**Why priority order matters:**
- Without it: random execution order can exhaust reserves inefficiently
- With it: largest risks are fixed first
- Margin stacking is visible (margin recalculated after each shield)

### Reserve Depletion Cascade (G39 — Shared Resource Protection)

**Reserve (30 lots) is SHARED across all shields in one beat.**

```
Beat N: Reserve = 30 lots

Shield 1 executes:
  loss = $500
  recovery_needed = 15 lots
  reserve now = 15 lots
  
Shield 2 executes:
  loss = $300
  recovery_needed = 12 lots
  BUT reserve only has 15 left
  → Create recovery with available 15 lots
  → reserve now = 0
  
Shield 3 tries to execute:
  loss = $200
  recovery_needed = 10 lots
  BUT reserve = 0
  → Reposition WITHOUT recovery
  → Alert: "Reserve exhausted. Tr3 repositioned without recovery."
```

**Logic:**

```python
for shield_to_execute in sorted_shields:
    loss = calculate_loss(shield)
    ce_recovery_needed = ceil(loss × 0.30 / new_ce_premium)
    pe_recovery_needed = ceil(loss × 0.70 / new_pe_premium)

    # Per-side independent availability check
    ce_available = session['ce_reserve_remaining']
    pe_available = session['pe_reserve_remaining']

    ce_alloc = min(ce_recovery_needed, ce_available)
    pe_alloc = min(pe_recovery_needed, pe_available)

    if ce_alloc > 0 or pe_alloc > 0:
        create_recovery_tranche(ce_alloc, pe_alloc)
        session['ce_reserve_remaining'] -= ce_alloc
        session['pe_reserve_remaining'] -= pe_alloc

        if ce_alloc < ce_recovery_needed or pe_alloc < pe_recovery_needed:
            Telegram: f"Reserve partially depleted. Tr{id} recovery reduced (CE:{ce_alloc}/{ce_recovery_needed}, PE:{pe_alloc}/{pe_recovery_needed})."
    else:
        # Both reserves exhausted — reposition without recovery
        reposition_without_recovery()
        Telegram: f"Reserve exhausted. Tr{id} repositioned without recovery."
```

**This prevents blindly failing; it degrades gracefully.**

### Beat Priority

**Shield fires BEFORE deployment.**  
If shield fires on beat N → deployment skipped until beat N+1.

---

## Automatic Hedging (Third Safety Layer) — Q43–Q50

**Purpose:** Buy protective spreads (long calls/puts) after deploying shorts. Caps definite loss in black swan scenarios.

**Philosophy:** Insurance policy. You pay premium NOW (hedge cost) to guarantee max loss LATER.

### Trigger & Execution

**When:** After tranche deployment completes successfully AND deployment capacity >= 50%:

```
CAPACITY THRESHOLD:
  Hedges only activate AFTER 50% of deployment budget committed
  - Total budget: 100 lots
  - Threshold: 50 lots (5 tranches)
  - Tr1–Tr4: NO hedges (hard stop provides protection)
  - Tr5+: Hedges activate (once 50 lots deployed)
  
  Rationale: Hard stop is the primary loss ceiling. Hedging cost is operational
             expense that should only start when significant capital is at risk.
             Saves ~$425 in hedge costs during Tr1–Tr4 phase.

IMPLEMENTATION:
  if total_deployed_lots >= 50:
    # Hedge this tranche
    schedule_hedge_execution(tranche_id)
  else:
    # Skip hedge (hard stop sufficient)
    log: f"Tr{tranche_id} deployed. Total: {total_deployed_lots} lots. Hedge threshold not met (need 50+)."

1. Record deployment completion:
   deployed_at = current_time()
   deployed_spot = current_spot
   deployed_tranche_id = 1 (or whatever)
   total_deployed_lots = SUM(lots for all tranches with type='deployment')

2. Check hedge threshold:
   if total_deployed_lots >= 50:
     # Schedule hedge execution (Tr5+)
     hedge_execute_at = deployed_at + hedge_execution_delay_minutes (default 15 min)
     Telegram: f"Tr{tranche_id} deployed. Total: {total_deployed_lots} lots. Hedge eligible (Tr5+). Scheduling in 15min."
   else:
     # Skip hedge (Tr1–Tr4)
     Telegram: f"Tr{tranche_id} deployed. Total: {total_deployed_lots} lots. Below 50% threshold—hedging deferred."
     return

3. At hedge execution time:
   
   a. Fetch live CE and PE strikes
   b. Compute hedge targets (based on CURRENT spot, not deployment spot):
      hedge_ce_target = current_spot × (1 + hedge_distance_pct / 100)
      hedge_pe_target = current_spot × (1 - hedge_distance_pct / 100)
      
      Example: current_spot = 70,000, hedge_distance = 20%
               hedge_ce_target = 70,000 × 1.20 = 84,000
               hedge_pe_target = 70,000 × 0.80 = 56,000
   
   c. Snap to nearest available strikes (live exchange API)
   
   d. Execute BUY orders (smart_execute):
      BUY tranche.ce.lots CE @ hedge_ce_strike
      BUY tranche.pe.lots PE @ hedge_pe_strike
      
      Order type: LONG (protective buy)
      Execution: Same smart_execute() with up to 4 reprice attempts
   
   e. Record hedge position in session['hedges']
   
   f. Track hedge cost:
      hedge_premium_paid = (ce_hedge_premium + pe_hedge_premium) × lots × LOT_SIZE
      Paid from margin (capital cost of doing business)
      NOT deducted from tranche premium_collected
```

### Hedge Position Structure

```python
session['hedges'] = [
    {
        'hedge_id': 'H-Tr1',
        'parent_tranche_id': 1,        # Links hedge to Tr1
        'type': 'hedge',               # Distinguishes from tranches + recovery
        'deployed_at': '2026-04-05T10:00:00+00:00',  # When Tr1 deployed
        'hedge_executed_at': '2026-04-05T10:15:00+00:00',  # When hedge bought
        'entry_spot': 70000,           # Market spot when hedge bought
        'hedge_distance_pct': 20.0,    # Configuration at execution time
        'ce': {
            'symbol': 'C-BTC-84000-010526',
            'strike': 84000,
            'lots': 10,                # SAME as parent tranche
            'entry_premium': 45.0,     # Cost to buy protection (LONG)
            'entry_delta': 0.35,
            'current_premium': None,   # Updated each beat
            'current_delta': None,
            'position_type': 'LONG',   # BUY to protect
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'status': 'ACTIVE',
            '_being_closed': False,
            '_being_closed_at': None,
        },
        'pe': {
            'symbol': 'P-BTC-56000-010526',
            'strike': 56000,
            'lots': 10,
            'entry_premium': 40.0,
            'entry_delta': -0.35,
            'current_premium': None,
            'current_delta': None,
            'position_type': 'LONG',   # BUY to protect
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'status': 'ACTIVE',
            '_being_closed': False,
            '_being_closed_at': None,
        },
        'hedge_premium_paid': 85.0,    # Total insurance cost (CE + PE)
        'spread_width_ce': 4000,       # 84K - 80K (sold strike - hedge strike)
        'spread_width_pe': 4000,       # 60K - 56K (sold strike - hedge strike)
        'max_loss_if_spreads_hit': 400,  # (spread_width × lots) = max loss value
        'status': 'ACTIVE',
    },
    # H-Tr2, H-Tr3, ... H-Tr10 created similarly
]

# Session aggregates
session['total_hedge_cost_paid'] = 850.0  # Sum of all hedge_premium_paid
session['active_hedges'] = 10             # Number of active hedge pairs (H-Tr1 through H-Tr10)
session['hedges_by_parent'] = {           # Quick lookup
    1: 'H-Tr1',
    2: 'H-Tr2',
    ...
}
```

### Three-Layer Protection Per Tranche

After Tr1 deployment + hedge execution:

```
Tranche 1 (Deployment):
  Sold CE @ 80K (short)
  Sold PE @ 60K (short)
  Premium collected: $100

Hedge H-Tr1 (Insurance):
  Bought CE @ 84K (long, 20% OTM)
  Bought PE @ 56K (long, 20% OTM)
  Insurance cost: $85

Result: TWO protective spreads
  CE Spread: Short 80K / Long 84K (capped loss if spot > 84K)
  PE Spread: Short 60K / Long 56K (capped loss if spot < 56K)
```

**Example: Black Swan (Market gaps to 59K)**

```
Without hedge:
  CE (sold @ 80K): worthless, loss = $140 × 10 = $1,400
  PE (sold @ 60K): ITM by 1K, loss = $10,000 (UNLIMITED as spot continues falling)
  Total loss: CATASTROPHIC

With hedge:
  CE spread: sold 80K / bought 84K
    If spot > 84K: max loss = (84K - 80K) × 10 = $400
    At spot 59K: both sides worthless on long, long CE expires worthless
    Loss = $400 (spread max)
  
  PE spread: sold 60K / bought 56K
    If spot < 56K: max loss = (60K - 56K) × 10 = $400
    At spot 59K: PE short loses $10K, PE long gains $5K, net loss = $5K
    But if spot continues to 50K, PE short → $100K loss, PE long → $60K gain
    Net loss capped at max spread value = $400 (theoretical)
    
  Total definite max loss: ~$800 (spread values)
  Hedge cost paid: $85
  Total actual max loss: ~$885 (insurance + spread cap)
```

### Critical Design: Hedge Close Policy (Q44–Q50)

**This is the key difference from regular tranches:**

```
Tranche closing rules:
  - Close when hard stop hits: YES
  - Close when DTE <= 7: YES
  - Close when profit target hit: YES (operator-driven)
  - Close when ATM Shield fires: YES (reposition)

Hedge closing rules:
  - Close when hard stop hits: NO (hedges survive)
  - Close when parent tranche closes: NO (hedge remains)
  - Close when DTE_CLOSE beat fires: YES, but only after all shorts are confirmed CLOSED
  - Close automatically outside DTE_CLOSE completion: NO
  
  Hedge closes only when:
    → ALL sold positions (all tranches) are completely closed (tranche.status = CLOSED)
    → AND there are NO pending sold positions
    → THEN DTE_CLOSE flow closes hedges to match
```

**Why hedges persist?**

```
Scenario 1: Tr1 closed via profit booking at +15%, but Tr2-Tr10 still open
  → Keep H-Tr1 active (market could reverse, need protection)
  → Don't close H-Tr1 until all Tr* are closed

Scenario 2: Hard stop hits, closes all short positions (Tr1-Tr10)
  → Hedges H-Tr1 through H-Tr10 remain OPEN
  → They're no longer hedging anything, but they're still open long positions
  → They'll decay to $0 at expiry (acceptable)
  → System doesn't forcefully close them

Scenario 3: DTE_CLOSE beat fires with shorts still open
  → System closes shorts first
  → After shorts are confirmed CLOSED, system closes hedges in same DTE_CLOSE flow
  → Session settles cleanly
```

**Session end:**

```
If Tr1-Tr10 all closed by expiry (DTE = 0):
  → Hedges H-Tr1-H-Tr10 also expire worthless
  → Session complete

If hard stop hit (closes all shorts but hedges remain):
  → Hard stop = COMPLETE (session ended)
  → Hedges are now ORPHANED (long positions without shorts)
  → System does NOT close them
  → They decay to $0 at expiry
  → This is acceptable: hedges are "insurance that expired"
```

### Margin & Cost Implications (Q43, Q45)

**Hedge cost is paid from margin:**

```
Example account:
  Total margin: $50,000
  Margin used by shorts: 80% = $40,000
  Margin available: 20% = $10,000

Deploy Tr1 (short 10 CE + 10 PE):
  Margin used: +$5,000 (example)
  Margin available: $5,000

Buy Hedge H-Tr1 (long 10 CE + 10 PE):
  Hedge cost: $850 (premium to pay)
  Margin impact: +$850 (long positions require margin too)
  Margin available: $4,150

Next deploy Tr2 (short 10 CE + 10 PE):
  Margin needed: $5,000
  Available: $4,150
  → BLOCKED (margin < 80% threshold violated)
```

**Implication:**
- Hedges consume margin
- Too many hedges → blocks new deployments (margin constrained)
- User controls hedge distance % → lower % = cheaper hedge = less margin
- Balance: protection vs deployment capacity

**NOT deducted from premium:**
- Hedge cost does NOT reduce total_premium_collected
- total_premium_collected = sum of shorts only
- Hard stop = 2.0 × total_premium_collected (based on shorts, not hedges)
- Hedge cost is operational expense, separate accounting

### Hedge Monitoring & Alerts (Q46–Q50)

**Hedges are monitored like tranches:**

```
Each heartbeat:
  - Update current_premium and current_delta for all hedge positions
  - Calculate unrealized P&L on hedges
  - Check if hedge strikes are still valid (haven't become ATM or ITM)
  - Telegram alerts:
    "H-Tr1 CE unrealized P&L: +$45 (premium decay, good)"
    "H-Tr3 PE delta: 0.42 (monitor for delta creep)"
    "H-Tr5: one of the sold positions closed, but hedge remains (as designed)"
```

**Hedges can become "unbalanced":**

```
If Tr1 gets repositioned by ATM Shield:
  Old Tr1 sold @ 80K CE / 60K PE → repositioned
  Tr1A recovery created
  
But H-Tr1 is STILL @ 84K CE / 56K PE (unchanged)

Result: H-Tr1 no longer protects Tr1 (different strikes)
        H-Tr1 might protect other tranches or no one

This is ACCEPTABLE:
  - Hedges don't move with shields
  - They remain as static "insurance" for original strikes
  - If those strikes get repositioned, the hedge is "displaced" but still alive
  - System logs this: "H-Tr1 displaced (Tr1 repositioned, Tr1A created)"
```

### Functional Requirements (Q51–Q60)

```python
# Test cases for hedging:

1. Hedge 50% capacity threshold (Q51 — NEW 2026-04-05)
   ✓ Tr1–Tr4 deployed: NO hedges (total = 10–40 lots)
   ✓ Tr5 deployed: Hedge activates (total = 50 lots, threshold met)
   ✓ Tr5–Tr10 deployed: Hedges continue (H-Tr5 through H-Tr10 active)
   ✓ Telegram: "Tr5 deployed. Total: 50 lots. Hedge eligible (Tr5+). Scheduling in 15min."

2. Deployment → 15min delay → Hedge buys (Tr5+ only)
   ✓ Tr5 deployed at 10:00 AM (after 50 lots total)
   ✓ H-Tr5 buys at 10:15 AM (not immediate)
   ✓ Tr1–Tr4 have NO hedges (hard stop protection sufficient)

3. Hedge distance configurable on WebUI
   ✓ User sets hedge_distance_pct = 15%
   ✓ System re-reads (hot-reload), next eligible hedge uses 15% OTM

4. Multiple hedges simultaneous (Tr5+)
   ✓ Tr5-Tr10 all deployed over time
   ✓ H-Tr5-H-Tr10 all active simultaneously (Tr1–Tr4 have NO hedges)
   ✓ Each hedge pair has separate strikes + premium

5. Hedge persists after tranche close (only active hedges)
   ✓ Tr5 closed via profit booking, H-Tr5 remains open
   ✓ Tr1–Tr4 never had hedges (below 50% threshold)
   ✓ H-Tr5+ persists until ALL Tr* closed

6. Hedge persists after hard stop (only active hedges)
   ✓ Hard stop hits, closes all Tr1-Tr10
   ✓ H-Tr5-H-Tr10 remain in system (H-Tr1-H-Tr4 don't exist)
   ✓ Session COMPLETE, hedges orphaned but alive

7. Margin consumed by hedges (Tr5+ only)
   ✓ Each hedge pair (Tr5+) uses margin (long positions)
   ✓ Tr1–Tr4 have zero hedge margin cost
   ✓ If hedges consume too much margin, next deployment blocked

8. Hedge cost NOT in hard stop calc
   ✓ total_premium_collected = shorts only (Tr1–Tr10)
   ✓ Hedge cost is separate (operational expense, Tr5+ only)

9. Hedges updated each beat (Tr5+ only)
   ✓ H-Tr5+ P&L recalculated, deltas updated
   ✓ Alerts sent if hedge strikes become threatening
   ✓ Tr1–Tr4 never have hedges (not updated)

10. Dashboard shows hedges separately (Tr5+ only)
    ✓ "Active Tranches" section (shorts Tr1–Tr10)
    ✓ "Active Hedges" section (longs H-Tr5–H-Tr10)
    ✓ Linked by parent_tranche_id
    ✓ Tr1–Tr4 show no hedges (below 50% threshold)

11. Telegram alerts on hedge execution (Tr5+ only)
    ✓ "H-Tr5 bought: CE @84K, PE @56K. Cost: $85. Insurance active."
    ✓ "H-Tr7 delta creep: PE now 0.55 (monitor)"
    ✓ Tr1–Tr4: "No hedge—capacity threshold not met (need 50 lots deployed)"
```

---

This is **Level 3 Protection** — the final safety layer before hard stop becomes the only option.

## Whipsaw Guard (Fourth Protection Layer — Oscillation Control)

**Purpose:** Prevent capital waste from deploying into oscillating markets (price ping-pongs between bull/bear, triggering multiple repositions without directional confirmation).

**MMMX Whipsaw Definition:**

A whipsaw is when:
1. Tranche deploys (e.g., Tr1 on 2% move)
2. Market retraces/oscillates back
3. ATM Shield fires unnecessarily (position still safe but market noise triggers reposition)
4. New recovery tranche created, capital allocated
5. Market oscillates again → more shield fires
6. Result: Capital tied up in recovery lots, deployment capacity lost, fees accumulating on repositions

**Examples (30-minute window, default parameters):**

```
Scenario 1 - Unnecessary Shield Fire:
  Beat 0 (10:00): Deploy Tr1 @ 67.5K, PE strike 60K (5% OTM buffer)
  Beat 1 (11:00): Spot 66.8K (retraced 1.1%), PE delta 0.35
                  OTM buffer = (67.5K - 60K) / 67.5K × 100 = 11.1% (still safe)
                  Decision: Shield does NOT fire ✓ (no whipsaw)
  
  BUT if market noise causes:
  Beat 1b (11:20): Spot 67.9K, PE delta drifts to 0.38
                   OTM buffer = (67.9K - 60K) / 67.9K × 100 = 11.6% (still safe)
                   Decision: Shield fires unnecessarily (noise, not trend) ✗ WHIPSAW
                   → Creates Tr1A (recovery), uses 5 lots from reserve
  
  Beat 2 (12:00): Spot 68.1K, PE delta 0.32 (back to safe)
                   Decision: Market recovered, Tr1A was wasted capital
                   Whipsaw score += 1

Scenario 2 - Oscillating Deployment:
  Beat 0: Spot 67.5K → Deploy Tr1 (CE + PE balanced)
  Beat 1: Spot 69.2K (2.5% move) → Deploy Tr2 (move justified)
          Tr2 deployed, PE becomes threatened (2% OTM)
  Beat 2: Spot 68.1K (retraced 1.6%) → PE shield fires
          Creates Tr1A (recovery on unnecessary reposition)
          Whipsaw score += 1
  Beat 3: Spot 69.8K (3% move from original 67.5K) → Would deploy Tr3
          BUT whipsaw score = 2 (CAUTION level)
          → Deployment triggers widened by 50%
          → Tr3 only deploys if move > 3% (not 2%)
          → Protects against chasing noise
```

### Four-Level Graduated Response

| Level | Score | Action | Effect |
|---|---|---|---|
| **NORMAL** | 0–1 | No restrictions | Deploy on normal triggers |
| **CAUTION** | 2 | Triggers widened +50% | Deploy move threshold: 2.0% → 3.0% |
| **RESTRICT** | 3 | Triggers widened +100% + halve lots | Move: 2.0% → 4.0%, tranche size: 10 → 5 lots |
| **COOLDOWN** | 4+ | Skip deployments for 1 interval | Pause new deployments for 1 hour, score decays -2 on expiry |

### Detection Logic

**Whipsaw detection tracks recent shield fires + oscillation:**

```python
# Session state additions:
session['_whipsaw_score'] = 0              # Current noise accumulation
session['_whipsaw_last_noise_at'] = None   # ISO timestamp of last whipsaw
session['_whipsaw_skip_until'] = None      # Cooldown expiry timestamp
session['_whipsaw_last_checked_idx'] = 0   # Last shield_event index evaluated
session['shield_event_history'] = []       # Track shield fires per beat

# Each beat, evaluate shield_event_history:
shield_window_mins = 30  # rolling 30-min window
spot_move_threshold_pct = 0.3  # noise threshold

for each shield_event in new events since last check:
    if event within last 30 mins:
        prev_event = shield_event_history[-1]
        spot_delta = abs(current_spot - prev_event.spot) / prev_event.spot × 100
        
        if spot_delta < 0.3%:  # Spot moved < 0.3% between shields
            # This is noise (not market confirmation)
            score += 1
            _whipsaw_last_noise_at = now
        
        # Also check direction flip (reposition on opposite side)
        if prev_event.side != current_event.side and spot_delta < 1.0%:
            # CE shield then PE shield with minimal move = oscillation
            score += 1
```

### Score Decay & Cooldown

**Score decays naturally over time:**

```
Rule: Every 1-hour heartbeat interval without a whipsaw event:
      score -= 1 (max decay -1 per interval)

Example:
  Beat 0: Whipsaw detected, score = 1, _whipsaw_last_noise_at = 10:00
  Beat 1 (11:00): No whipsaw, 1 interval elapsed, score -= 1 → score = 0 ✓
  
  Beat 0: Whipsaw detected, score = 1
  Beat 0b (10:45): Another whipsaw (15min later), score += 1 → score = 2 (CAUTION)
  Beat 1 (11:00): No whipsaw, 1 interval elapsed, score -= 1 → score = 1
  Beat 2 (12:00): No whipsaw, score -= 1 → score = 0

Cooldown Expiry:
  Beat X: Score reaches 4 (COOLDOWN), set _whipsaw_skip_until = now + 1 hour
  Beat X+1 (1h later): Cooldown expired
                       Score -= 2 as reward (4 → 2)
                       Clear _whipsaw_skip_until
                       Resume normal operation
```

### Implementation Details

**CAUTION Level (Score 2):**
- Deployment trigger move threshold widened: 2.0% → 3.0%
- ATM Shield threshold tightened: OTM buffer still 5%, but require delta confirmation
- No other restrictions; session continues normally

**RESTRICT Level (Score 3):**
- Deployment trigger move threshold: 2.0% → 4.0%
- Tranche size halved: 10 lots → 5 lots (reduce capital waste on noise)
- ATM Shield still fires normally (protection priority)
- Session continues with reduced offensive actions

**COOLDOWN Level (Score 4+):**
- All new deployments SKIPPED for 1 hour
- Deployment Eligibility Queue cleared (queued tranches reset)
- ATM Shield STILL FIRES (protection > offense)
- Hard stop STILL FIRES (protection > offense)
- After 1 hour: skip_until expires, score decays -2, resume

**Why score 4+ uses only 1 interval cooldown (not full pause):**
- MMM algo uses full session PAUSE (no orders placed) → too aggressive for monthly (30–45 DTE)
- MMMX uses interval-skip (deployment blocked, but everything else runs) → safer, still allows defense
- If score reaches 4+ again during cooldown → cooldown extends

### Parameters (Hot-Reloadable)

```python
'whipsaw_window_mins': 30,           # Rolling window to detect oscillation
'whipsaw_spot_move_pct': 0.3,        # Noise threshold (moves < this = noise)
'whipsaw_caution_score': 2,          # Score threshold for CAUTION level
'whipsaw_restrict_score': 3,         # Score threshold for RESTRICT level
'whipsaw_cooldown_score': 4,         # Score threshold for COOLDOWN level
'whipsaw_cooldown_interval_hours': 1, # Duration of skip-interval on COOLDOWN
```

### Telegram Alerts

```
CAUTION: "Whipsaw CAUTION (score 2): market oscillating. Deployment triggers widened +50%."
RESTRICT: "Whipsaw RESTRICT (score 3): repeated oscillation. Triggers widened +100%, lot size halved."
COOLDOWN: "Whipsaw COOLDOWN (score 4): pausing new deployments for 1 hour to let noise settle."
RECOVERY: "Whipsaw score decayed to {new_score}. CAUTION level cleared, resuming normal deployment."
```

### Why Whipsaw Guard Matters for MMMX

Without guard:
- Operator sees 6% move, deploys Tr1–Tr3 via queue
- Market oscillates 6% back and forth
- Shield fires multiple times on each oscillation
- Reserve depleted on unnecessary recovery lots
- Deployment capital wasted on noise entry points
- Fees accumulate on pointless repositions

With guard:
- First whipsaw detected → score increments
- Score reaches 2–3 → deployment triggers automatically widen
- Market oscillation still triggers shield (protection intact)
- But no new deployments waste capital
- Only real directional moves (> widened threshold) deploy
- Capital preserved for quality opportunities

---



## Dual-Stream Monitoring

MMMX runs two independent threads in parallel:

```
┌─────────────────────────────────────┐
│ THREAD 1: Scheduled Heartbeat       │
│ • Every 1 hour (base cadence)       │
│ • Evaluates all triggers            │
│ • Rolls / reduces / deploys         │
│ • Updates state                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ THREAD 2: Real-Time Listener        │
│ • Continuous data-driven            │
│ • Watches live bid/ask on active    │
│   CE and PE strikes                 │
│ • Tier-0 circuit breakers (4)       │
│ • Wakes heartbeat OR reduces        │
│   immediately (delta >= 0.72)       │
└─────────────────────────────────────┘
```

### Heartbeat Flow (1-hour cadence)

```
1. Load fresh session from storage + generation check (stale monitor guard)
2. Fetch live data: premiums, deltas, spot, DVOL, DTE, IV rank, margin
3. Run safety checks (DTE validity, generation, etc.)
4. Update P&L for all positions + portfolio delta
   (if P&L data incomplete → skip triggers, retry next beat)
5. Hard stop check — if hit → close_all, COMPLETE, return
6. DTE check — if DTE <= close_at_dte → close_all, COMPLETE, return
7. ATM Shield check — for each position
   if remaining_otm < threshold → execute shield
   if shield fires → skip deployment this beat
8. Deployment check (if NOT shield_fired)
   check_deploy_conditions() — if pass → deploy tranche
9. Evaluate remaining triggers (delta drift, IV spike, reposition/roll, portfolio delta)
10. Save state + emit WebSocket events + Telegram
11. Schedule next beat (1 hour later)
```

**If `_force_check=True` set by premium listener → run full beat immediately (outside schedule).**

### Real-Time Premium Listener (G27)

Runs continuously. Subscribes to WebSocket for live bid/ask on active CE and PE strikes.

**Tier-0 Circuit Breakers (Evaluated Every Tick, ~1–2 seconds):**

| Breaker | Condition | Action |
|---|---|---|
| `CB_PREMIUM_JUMP` | Side premium jumped > 40% since last beat | Force heartbeat (wake immediately) |
| `CB_DELTA_BLOWOUT` | Position delta > 0.45 (moved unexpectedly fast) | Force heartbeat |
| `CB_IV_FLASH_SPIKE` | IV rank jumped > 50% | Force heartbeat |
| `CB_NEAR_ITM` | Delta >= 0.72 (near ITM, uncontrollable) | Immediate 50% emergency reduce (do NOT wait for heartbeat) + then force heartbeat |

**Why not close all on CB?**  
CB only detects that something significant happened. It doesn't know whether it's recoverable. Let the heartbeat run its full decision logic (with delta gates) to decide the right action.

**Exception: `CB_NEAR_ITM`** — delta >= 0.72 is so dangerous (gamma → infinity) that we immediately reduce 50% without waiting. Then force heartbeat for full assessment.

**Force heartbeat wakes the monitor thread** → run full beat immediately instead of waiting 1 hour.

### Listener vs Heartbeat Priority (Q18)

**Heartbeat has priority.** The listener's role is detection and waking — the heartbeat's role is decision-making. They never "conflict" because the listener does not execute deployment or protection logic on its own (exception: `CB_NEAR_ITM` emergency reduce).

When both trigger at the same time:
1. Listener sets `_force_check=True` and (if `CB_NEAR_ITM`) executes the 50% emergency reduce.
2. Heartbeat thread wakes, runs its FULL beat logic — hard stop check, shield check, deployment check, all triggers.
3. Any CB state the listener recorded is visible to the heartbeat (both conditions are evaluated by heartbeat).

**Why heartbeat wins:** The heartbeat evaluates all conditions together with delta gates, trigger priority order, and position context. The listener only knows one metric changed. Defer all consequential decisions to the heartbeat.

### Generation Guard (Stale Monitor Prevention)

**Three-layer guard (from MMM P0 incident — CLAUDE.md §4):**

1. **`_run_loop` top check:** Each beat, load fresh session from storage. Verify `stored_gen > self._my_generation`. If stale → stop, Telegram, break.
2. **`_save_session()` return value:** Returns True/False. Caller must check and abort if save rejected.
3. **Pre-action generation verify:** Before any exchange order, re-check generation. If stale → abort, no mutation.

**Result:** A stale monitor instance can NEVER place orders.

### Heartbeat Delay Watchdog (G41 — WebSocket Liveness Check)

**Premium Listener must receive live price updates. If it doesn't → undetected risk.**

```python
# In listener main loop:

last_price_update = current_time()

while listening:
    if new_price_received:
        last_price_update = current_time()
    
    # Check: has price update gone stale?
    time_since_update = current_time() - last_price_update
    
    if time_since_update > 300 seconds:  # 5 minutes
        # WebSocket is stale → force heartbeat immediately
        set _force_check = True
        send_alert: "WebSocket stale (5min no update). Forcing heartbeat."
        
        # Also check heartbeat isn't dead
        if last_heartbeat_time > 300 seconds:
            # BOTH are stale — emergency situation
            send_telegram_critical: "Monitor unresponsive (5min). Manual check required."
```

**Why 5 minutes?**
- Heartbeat is 1 hour normally
- If listener is dead for 5+ min, real P&L could have moved 5–10% undetected
- Force heartbeat immediately to check actual state

**What forces heartbeat:**
- CB fires (premium jump, delta blowout, IV spike, near ITM)
- WebSocket price update goes stale (>5 min)
- Both are data-driven triggers

**Telegram alerts:**
```
Normal: "WebSocket stale (5min no price). Forcing heartbeat."
Critical: "Monitor unresponsive (heartbeat + listener both stale). Operator check needed."
```

---

# SECTION 5: TRIGGER EVALUATION (Heartbeat Decisions)

**All triggers below assume threatened-side delta is the primary gating variable.**

### Delta Gate (Rules All Actions)

```
if threatened_delta >= 0.70:
  action = CLOSE_ALL  # Near ITM, unmanageable
elif threatened_delta >= 0.55:
  action = REDUCE_THEN_ROLL  # Threatened, reduce first
elif threatened_delta >= 0.35:
  action = REPOSITION  # Market moved, rebalance
else:
  action = None  # Normal zone, no delta-based action
```

### Trigger Priority (First Match Wins)

| # | Trigger | Condition | Action |
|---|---------|-----------|--------|
| 1 | DTE_CLOSE | DTE <= close_at_dte (default 7) | close_all (shorts); hedges close after all shorts confirmed CLOSED |
| 2 | HARD_STOP | total_pnl <= -hard_stop_usd | close_all shorts; hedge LONGs survive (orphaned) |
| 3 | IV_CATASTROPHE | IV change >= 80% AND threatened_delta >= 0.70 | close_all |
| 4 | NEAR_ITM | max_threatened_delta >= 0.70 | close_all |
| 5 | DEPLOY_TRANCHE | check_deploy_conditions() passes | deploy |
| 6 | IV_SPIKE | IV change >= 50% AND threatened_delta >= 0.55 | reposition |
| 7 | REPOSITION | Directional move detected, delta 0.35–0.69 | reposition |
| 8 | PORTFOLIO_DELTA | abs(portfolio_delta) >= threshold | reduce worst |
| 9 | DELTA_DRIFT | \|current_delta - entry_delta\| > delta_drift_threshold | roll |

**First match wins.** Evaluation stops at the first trigger that fires.

> **Note:** `SIDE_LOSS` (per-tranche loss trigger) was removed. Hard stop is the sole protection against position losses — it fires on portfolio `total_pnl` and closes all SHORT legs when breached. No separate per-tranche reduce trigger is needed.

### Key Trigger Notes

**DEPLOY_TRANCHE (Priority 5):** OR logic (spot move alone OR IV spike alone is sufficient). Deploys next 10% tranche when market confirms opportunity.

**IV_SPIKE & REPOSITION:** High IV is an OPPORTUNITY. Reposition means: roll profitable side forward (collect elevated IV), roll threatened side farther OTM (reduce delta). Never close all just because IV is high.

**NEAR_ITM (Priority 4):** Only delta >= 0.70 triggers close-all. Below that, reduce and reposition.

**DELTA_DRIFT (Priority 9):** Checks the profitable side's drift from its 20Δ entry target using `|current_delta - entry_delta| > delta_drift_threshold`. Lowest priority — fires only when no other trigger applies.

---

# SECTION 6: EXECUTION FUNCTIONS

## Smart Execution (`mmmx_executor.py`)

**Mid-price entry with reprice loop (same as MMM):**

```python
async def smart_execute(symbol, side, size, reduce_only=False,
                        max_reprice_attempts=4):
    """
    1. Place limit order at mid-price
    2. Wait FILL_TIMEOUT (60s)
    3. If not filled:
       • Reprice to best bid/ask (more aggressive)
       • Retry (up to max_reprice_attempts)
    4. Fall back to emergency_execute() if all attempts fail
    5. Return: {success, filled_size, fill_price, attempts, total_time_ms}
    """
```

**Dedup (G8):** Every order gets deterministic `client_order_id`. Check if pending on exchange before placing — skip if already pending.

**Margin pre-check (G6):** Before any SELL order, fetch margin utilization. Block if > 80%.

**Continuous Margin Re-Check During Execution (G40):**

Margin can spike during execution (5-min reprice loop). System must check continuously:

```python
async def smart_execute(symbol, side, size, reduce_only=False, max_reprice_attempts=4):
    """
    1. Pre-execution margin check (current logic)
    2. Place limit order at mid-price
    3. For each reprice attempt:
       a. Wait 30s for fill
       b. Before next reprice: RE-CHECK margin
       c. If margin > 85%: ABORT reprice, place market order immediately
       d. If margin > 95%: ABORT execution, return failure
    4. Fall back to emergency_execute() if all attempts fail
    """
```

**Margin re-check frequency:**
- Before EACH reprice attempt (every 30s)
- If margin jumps 70% → 85%: switch to market order (faster execution)
- If margin hits 95%: abort order, return FAILURE
  → Let caller decide: reduce position? or wait?

**Why this matters:**
- IV spike = margin requirement spikes
- Without re-check: you can execute a sell order that breaches margin mid-execution
- With re-check: you switch to market order before margin becomes critical

**Telegram alerts:**
```
"Margin spike during execution: 72% → 88%. Switched to market order."
"Margin critical (95%) during reprice. Execution aborted. Manual intervention needed."
```

## Deployment Execution

```python
async def execute_tranche_deploy(session, spot, iv_rank, dvol):
    """
    1. Compute new strikes from current spot + live chain
    2. Calculate lots (10% of budget)
    3. [PRE-FLIGHT] Deployment frequency gate (Q30):
       - Count deployments in last 24 hours
       - If count >= max_deployments_per_day (default 2): skip deployment, Telegram alert, return
       - Reason: prevent chasing slow trends; 2 deployments/day is aggressive enough
    4. [PRE-FLIGHT] Liquidity fairness gate (Q_FAIRNESS):
       - Fetch live bid/ask for computed CE and PE strikes
       - Calculate Black-Scholes theoretical price (using dvol)
       - Check: abs(mid - bs_price) / bs_price <= fairness_threshold (default 10%)
       - If fails and fairness_gate_enabled: skip deployment, Telegram alert, return
       - If passes or gate disabled: continue
    5. Sell CE via smart_execute()
    6. Sell PE via smart_execute()
    7. If either fails: no state mutation, return
    8. On success:
       - Add new tranche to session['tranches']
       - Update hard_stop_usd
       - Emit WebSocket + Telegram
    """
```

**Deployment Frequency Gate (Q30):**

When enabled (default), limits new deployments to prevent chasing slow trends:
- **Check:** How many NEW tranches were deployed in the last 24 hours?
- **Limit:** `max_deployments_per_day` (default: 2)
- **If exceeded:** Skip deployment this beat. Telegram: "Max deployments reached today. Next deployment available at {next_window}."

**Why this gate:**
- Slow BTC moves (1% every 3–4 hours) accumulate to 8% over 2 days.
- Without this, you deploy every beat → transaction costs exceed premium captured.
- 2 deployments per day is aggressive; 3+ per day chases the trend.

**Fairness Gate Logic (Q_FAIRNESS):**

When enabled, before placing any deployment order:
- Compute theoretical fair value using Black-Scholes with current `dvol`
- Fetch live bid/ask from exchange
- Calculate mid-price = (bid + ask) / 2
- Check: `|mid - bs_price| / bs_price <= fairness_threshold`
- If check fails: **Deployment skipped for this beat.** Telegram: "Deployment on hold — market liquidity below fairness threshold. Retrying next beat."

**Why this gate:**
High IV + thin liquidity is a trap. The signal is real (IV is high) but the execution is bad (wide spread). This gate prevents deploying into broken markets.

**When it triggers:**
- Spread > 10% and quote is stale → mid is 8–12% worse than BS
- Depth < 5 lots and mid slips → low conviction on pricing
- Flash crash scenario where BS ≠ mid

**When it's safe to disable:**
- Market is very liquid (depth >= 20 lots, spread < 3%)
- You trust live API quotes
- You want to deploy on any high IV regardless of spread

Default: **ENABLED** (safety first). Operator can hot-reload to DISABLED if desired.

## Reposition Execution (G28)

**Called when threatened_delta is 0.35–0.69 (manageable but not safe).**

Identifies profitable side (deep OTM) and threatened side (approaching ATM).

**Step 1: Roll profitable side forward**
- Buy back profitable side at cheap premium
- Sell new position at new ATM-adjacent strike
- Collect elevated IV premium

**Step 2: Roll threatened side farther OTM**
- Buy back threatened side at expensive premium
- Sell new position at farther OTM strike (reduce delta)
- Collect some premium (reduces loss on the roll)

**Step 3: If any step fails:**
- Session PAUSED + NAKED ALERT + Telegram

## Reduce_Then_Roll (When threatened_delta >= 0.55)

**Before repositioning, reduce exposure.**

```
Step 1: Buy back 50% of threatened side (minimum 1 lot)
Step 2: Roll profitable side forward (same as reposition Step 1)
Step 3: Reassess remaining threatened side
        if still >= 0.55: schedule force_check in 1h (monitor closely)
        if < 0.55: normal cadence resumes
```

## Profit Booking (Per-Tranche Selective Close) — Q29/Q32/Q34

**New capability:** Operator can manually close individual profitable tranches at tranche-specific profit thresholds to book gains and create deployment capacity for future tranches.

**Key Design: Per-Tranche Level (NOT portfolio-level)**

Profit booking is **entirely per-tranche**, not global. Each tranche is evaluated independently:

```
Tranche 1: P&L = +$18 → Target 15% → Close if profit ≥ $15
Tranche 2: P&L = +$12 → Target 30% → Hold (wait for $30 profit)
Tranche 3: P&L = +$5  → Target 10% → Close if profit ≥ $10
```

**How it works:**

```
1. Operator opens MMMX dashboard → "Profit Booking" tab
2. Sees all active tranches listed with:
   - Tranche ID (Tr1, Tr2, Tr2A recovery, etc.)
   - Entry spot + premium collected
   - Current P&L ($) and P&L (%)
   - Entry date, current DTE
3. For each tranche, operator can:
   - Select tranche checkbox
   - Pick target profit % from [10, 20, 30, 50]
   - Click "Close at Target"
4. System executes (for each selected tranche):
   - Buys back CE and PE at selected tranche
   - If P&L ≥ target, close immediately
   - If P&L < target, either:
     a) Queue pending close (monitor until P&L hits target, then close)
     b) Close now anyway (operator override)
   - Books the profit
   - Removes tranche from session['tranches']
   - Frees up capital + deployment count
   - Telegram: "Tranche 1 closed at +15% profit ($15). Capital available for future deployment."
5. Next beat: freed deployment slot can be used for new tranche if triggers fire
```

**Design Details:**

- **Per-tranche granularity:** Each tranche is independent. No "portfolio-level close."
- **Operator discretion:** Manual selection (not automatic). Operator chooses WHICH tranches to close and AT WHAT PROFIT TARGET.
- **Hot-reloadable:** `profit_booking_targets` = [10, 20, 30, 50] (%) — predefined thresholds for quick selection. Operator can adjust list.
- **Smart execution:** Uses same smart_execute() with up to 4 reprice attempts.
- **No impact on hard stop:** Closing a tranche reduces portfolio risk → hard stop recalculates lower.
- **Recovery tranches (2A, 2B, 2C):** Can be closed independently at their own profit targets. Profit from recovery booked separately.

**Example progression (per-tranche):**

```
Beat 0: Deploy Tr1, premium = $100, hard_stop = $200
        Deploy Tr2, premium = $95, hard_stop = $390

Beat 5: Tr1 P&L = +$18 (18% profit)
        Tr2 P&L = +$8 (8% profit)
        
        Operator selects:
          - Tr1 target: 15% → Close now (profit $18 ≥ $15)
          - Tr2 target: 20% → Hold (profit $8 < $19, not yet)
        
        System: Closes only Tr1
        Result: 
          - Tr1 closed, $18 booked
          - tranches_deployed -= 1 (Tr2 still live)
          - hard_stop recalculated: = 2.0 × ($95 remaining) = $190
          - Capital freed (1 deployment slot available)
        
        Telegram: "Tr1 closed at +15% profit (+$18). Tr2 still live (+8% profit)."

Beat 6: Tr2 P&L = +$22 (23% profit)
        Operator selects:
          - Tr2 target: 20% → Close now (profit $22 ≥ $19)
        
        System: Closes Tr2
        Result: Capital freed, hard_stop scales down further
        
        Deployment available: Can deploy Tr3 if triggers fire
```

**Why this feature (vol crush scenario — Q29):**
- Vol crush = IV spikes then collapses → positions profitable on both theta AND vega
- Operator sees tranches in profit (e.g., +15%, +18%, +25%)
- Manually closes the best performers at selected targets
- Books gains incrementally (not all at once, not at fixed portfolio level)
- Frees capital to redeploy into fresh tranches or reduce risk
- **No emotion:** Targets are predefined; operator just clicks

**Why per-tranche (not portfolio-level):**
- Different tranches have different entry spots, premiums, deltas
- One tranche might be +25% while another is -5%
- Forcing a portfolio-level close wastes winning positions
- Per-tranche granularity lets operator book winners independently

---

# SECTION 7: SESSION STATE MODEL

## CE/PE Lot Imbalance Monitoring (G42 — Structural Risk)

**Problem:** After multiple recoveries, CE and PE lots can become skewed (e.g., CE=5, PE=45) even if delta looks OK.

**Solution:** Track structural imbalance alongside delta.

```python
# Calculate at every beat:

total_ce_lots = SUM(tranche.ce.lots for all tranches)  # includes recovery tranches
total_pe_lots = SUM(tranche.pe.lots for all tranches)

lot_ratio = total_ce_lots / total_pe_lots  # should be ~1.0 (balanced)

imbalance_pct = abs(1.0 - lot_ratio) × 100

# Gate:
if imbalance_pct > 40%:
    # Structural imbalance too severe
    # Examples: CE=10, PE=50 (80% imbalanced)
    Telegram: f"Lot imbalance: CE={total_ce_lots}, PE={total_pe_lots} ({imbalance_pct:.0f}% skewed)"
    
    # Decision:
    if imbalance_pct > 60%:
        # Critical imbalance — apply defensive action
        # Reduce the over-represented side (sell more of the one with more lots)
        reduce_larger_side()  # or alert operator
```

**Why this matters:**
- Delta ≥ 0.70 triggers close-all
- But if you have CE=5, PE=50:
  - Portfolio delta might be 0.30 (delta-safe)
  - But PE is structurally dominant (7× more lots)
  - A sudden move hits PE much harder
  - Delta gates don't capture structural risk

**Monitoring in session state:**

```python
session['ce_lot_balance'] = {
    'total_ce_lots': total_ce_lots,
    'total_pe_lots': total_pe_lots,
    'imbalance_pct': imbalance_pct,
    'last_rebalance_beat': beat_number,
}
```

**This is for awareness, not hard stop.** You'll see it in dashboard + Telegram alerts.

## Tranche Structure (Multiple Positions Per Tranche)

```python
session['tranches'] = [
    {
        'tranche_id': 1,
        'deployed_at': '2026-04-04T10:00:00+00:00',
        'entry_spot': 67500,
        'entry_dvol': 52.0,
        'entry_iv_rank': 65,
        'ce': {
            '_pos_id': 'abc12345',
            'symbol': 'C-BTC-77625-010526',
            'strike': 77625,
            'lots': 10,
            'entry_premium': 140.0,
            'entry_delta': 0.20,
            'current_premium': None,  # updated each beat
            'current_delta': None,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'status': 'ACTIVE',  # or CLOSED, REDUCED, REPOSITIONED
            '_being_closed': False,  # in-flight guard, 180s TTL
            '_being_closed_at': None,
        },
        'pe': { ... },  # same structure as ce
        'premium_collected': 275.0,  # (ce + pe) × lots × LOT_SIZE
        'status': 'ACTIVE',  # or PARTIAL, CLOSED
    },
    { ... },  # Tranche 2, deployed later
    {
        'tranche_id': '2A',          # Sibling recovery tranche — created by ATM Shield on Tranche 2
        'parent_tranche_id': 2,
        'type': 'recovery',          # 'deployment' for regular tranches, 'recovery' for shield-created
        'shield_event': 1,           # First shield event on Tranche 2
        'deployed_at': '2026-04-05T14:30:00+00:00',
        'entry_spot': 70000,
        'ce': {
            '_pos_id': 'xyz99999',
            'symbol': 'C-BTC-78500-010526',
            'strike': 78500,
            'lots': 3,               # 30% of loss offset
            'entry_premium': 95.0,
            'entry_delta': 0.18,
            'current_premium': None,
            'current_delta': None,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'status': 'ACTIVE',
            'shift_count': 0,        # Own counter — independent of Tranche 2's shift_count
            '_being_closed': False,
            '_being_closed_at': None,
        },
        'pe': {                      # 70% of loss offset goes to PE side
            'lots': 7,
            ...                      # same structure as ce
        },
        'premium_collected': 95.0,   # Contributes to total_premium_collected (hard stop scales)
        'status': 'ACTIVE',
    },
    # If Tranche 2 triggers ATM Shield again → Tranche 2B created (same structure)
    # Third time → Tranche 2C (max_shifts = 3 = max siblings per parent)
]

# Aggregates
session['total_premium_collected'] = 1170.0  # Includes recovery tranche premiums
session['total_deployed_lots'] = 20
session['tranches_deployed'] = 2             # NOT incremented for recovery tranches
session['tranches_remaining'] = 8            # NOT decremented for recovery tranches
session['hard_stop_usd'] = 2340.0
session['last_deployment_spot'] = 70500
session['last_deployment_iv_rank'] = 73
session['portfolio_delta'] = 0.15            # combined
session['ce_reserve_remaining'] = 30         # CE shield reserve lots remaining (per-side)
session['pe_reserve_remaining'] = 30         # PE shield reserve lots remaining (per-side)

# Whipsaw Guard State
session['_whipsaw_score'] = 0                    # Noise accumulation score (0–4+)
session['_whipsaw_last_noise_at'] = None        # ISO timestamp of last detected whipsaw
session['_whipsaw_skip_until'] = None           # ISO timestamp, skip deployments until this time (COOLDOWN mode)
session['_whipsaw_last_checked_idx'] = 0        # Last shield_event_history index evaluated
session['shield_event_history'] = []            # List of recent shield fires: [{'beat': N, 'side': 'ce', 'spot': 70000, 'timestamp': '...'}]
```

## Timestamps (UTC-Only Mandate)

All timestamps use `datetime.now(timezone.utc)` — never naive `utcnow()`. Format includes `+00:00` suffix.

**DTE Computation:**
```
dte_days = (expiry_datetime - datetime.now(timezone.utc)).total_seconds() / 86400
```

## Parameter Defaults (Hot-Reload Allowlist)

**Entry gates (not hot-reloadable):**
- `entry_dte_min` = 20, `entry_dte_max` = 45
- `entry_iv_rank_min` = 50

**Tranche deployment (hot-reloadable):**
- `total_budget_lots` = 100
- `tranche_pct` = 10  (%)
- `otm_distance_pct` = 15  (%)
- `tranche_deploy_move_pct` = 2.0  (%)
- `tranche_deploy_iv_delta` = 10  (rank points)
- `hard_stop_multiplier` = 2.0  (minimum 1.0)

**Heartbeat (hot-reloadable):**
- `adjustment_interval_hours` = 1

**Delta gates (hot-reloadable):**
- `delta_drift_threshold` = 0.35
- `portfolio_delta_threshold` = 0.15
- `near_itm_delta` = 0.55
- `emergency_delta` = 0.70

**IV controls (hot-reloadable):**
- `iv_spike_threshold_pct` = 50
- `iv_catastrophe_pct` = 80  (must be > iv_spike)

**ATM Shield (hot-reloadable):**
- `atm_protect_threshold` = 5.0  (%)
- `atm_shield_max_shifts` = 3

**Deployment Quality Gates (hot-reloadable):**
- `fairness_gate_enabled` = True  (liquidity fairness check)
- `fairness_threshold_pct` = 10.0  (%) — max acceptable mid vs BS deviation
- `max_deployments_per_day` = 2  (frequency gate: max 2 new tranches per 24h to prevent chasing slow trends)

**Profit Booking (per-tranche, hot-reloadable):**
- `profit_booking_enabled` = True  (operator can selectively close individual tranches at profit targets)
- `profit_booking_targets` = [10, 20, 30, 50]  (%) — per-tranche profit thresholds (operator selects target for EACH tranche independently)

**Hedging (per-tranche insurance, hot-reloadable):**
- `hedging_enabled` = True  (automatic hedge buying after tranche deployment)
- `hedge_distance_pct` = 20.0  (%) — user-defined OTM distance for hedge strikes (10–50% range, hot-reloadable on WebUI)
- `hedge_execution_delay_minutes` = 15  (minutes after tranche deployment to buy hedges, hot-reloadable)

**Exit controls (hot-reloadable, but `close_at_dte >= 7` hard-enforced):**
- `close_at_dte` = 7  (minimum, non-negotiable)
- `profit_target_pct` = 50
- `profit_target_enabled` = False

---

# SECTION 8: FILE STRUCTURE

## Backend Files (23 total, ~7,170 lines)

### Foundation (Storage, Config, Constants)
- `mmmx_constants.py` — `LOT_SIZE_BTC`, shared constants
- `mmmx_state.py` — Session state model + defaults
- `mmmx_config.py` — Parameter validation + `close_at_dte >= 7` enforcement
- `mmmx_storage.py` — SQLite persistence (`mmmx_sessions.db`)

### Activity & Audit Logging
- `mmmx_activity.py` — Activity log ring buffer
- `mmmx_audit_log.py` — Append-only trade event journal
- `mmmx_param_audit.py` — Every hot-reload param change logged

### Communication
- `mmmx_websocket.py` — WebSocket event emitters (all `mmmx_*` prefixed)
- `mmmx_telegram.py` — Alert system with dedup

### Core Engine
- `mmmx_engine.py` — Monthly math: sigma strikes, P&L, portfolio delta, IV change
- `mmmx_trigger.py` — Priority-ordered trigger evaluation
- `mmmx_safety.py` — Pre-beat checks, DTE sanity, generation guard
- `mmmx_executor.py` — Smart execution + dedup + margin pre-check

### Protection
- `mmmx_atm_shield.py` — OTM buffer monitoring + buyback + reposition + recovery lots

### Monitoring & Infrastructure
- `mmmx_circuit_breaker.py` — 3-state API fault isolation
- `mmmx_monitor.py` — Heartbeat thread + generation tracking + health grading
- `mmmx_premium_listener.py` — Real-time WebSocket listener + Tier-0 circuit breakers
- `mmmx_watchdog.py` — Supervisor (detects + restarts dead threads)

### Entry & Initialization
- `mmmx_initializer.py` — Entry gates + strike scanning + order flow + reconciliation
- `mmmx_margin_guardian.py` — Wrapper around `MarginGuardian` for MMMX

### API & Registration
- `mmmx_api.py` — REST endpoints (`/api/mmmx/*`)
- `__init__.py` — Blueprint registration + session restore on startup
- `tests/` — Unit tests

## Frontend Files (4 total)

- `MMMXContext.js` — React context + WebSocket listeners
- `useMMMXWebSocket.js` — Custom hook for WebSocket subscription
- `mmmxService.js` — API client (axios)
- `MMMXDashboard.js` — MVP dashboard (status, tranches, risk, P&L, adjustment history)

## Integration Points (Zero Modification to MMM Files)

| File | Change |
|---|---|
| `webui/backend/app.py` | Register MMMX blueprint in isolated try/except AFTER MMM block |
| `webui/frontend/src/App.js` | Add MMMX lazy import + tab + route |
| `webui/frontend/src/config/navigationSections.js` | Add MMMX nav entry |

---

# SECTION 9: ISOLATION & SAFETY CHECKS

## Isolation Rules (Must Pass Before Go-Live)

✓ **No MMM runtime imports** inside `webui/backend/routes/mmmx/` (automated scan)  
✓ **Separate database** — `mmmx_sessions.db`, never reads `mmm_sessions.db`  
✓ **Separate registry** — `_mmmx_monitors` dict, not shared with MMM's `_monitors`  
✓ **Separate WebSocket namespace** — all events `mmmx_*`, never `mmm_*`  
✓ **No cross-contamination** — MMM knows nothing about MMMX  
✓ **Sealed tests unchanged** — MMM test suite still passes 100%  

## Functional Tests (Required)

- [ ] Param validation: `close_at_dte=5` rejected with gamma-risk message
- [ ] Param validation: `close_at_dte=7` accepted
- [ ] Entry gates block session if DTE < 20 or > 45
- [ ] Entry gates block session if IV rank < 50
- [ ] Deployment OR logic: spot move alone triggers deployment
- [ ] Deployment OR logic: IV spike alone triggers deployment
- [ ] Deployment frequency gate: max 2 deployments per 24h enforced
- [ ] Deployment frequency gate hot-reload: can change limit live
- [ ] Fairness gate enabled: deployment skipped if mid > BS by 10%+
- [ ] Fairness gate disabled: deployment proceeds despite wide spread
- [ ] Profit booking (per-tranche): Tr1 at 15% target closes while Tr2 at 20% holds (independent evaluation)
- [ ] Profit booking: operator selects multiple tranches, each at own target (not portfolio-level)
- [ ] Profit booking frees deployment capacity: closed tranche slot available for new deployment
- [ ] Profit booking recalculates hard stop: risk decreases after close
- [ ] Profit booking on recovery tranche: Tr2A (recovery) closed independently of Tr2 (parent)
- [ ] Hard stop scales: after 3 tranches, hard stop grows 3× larger
- [ ] Portfolio hard stop (Q33): if total_pnl ≤ -hard_stop_usd, close ALL tranches + ALL recovery
- [ ] Hard stop closes recovery tranches too: no partial hedges left
- [ ] Hard stop cannot be overridden: no manual "wait" allowed
- [ ] ATM Shield fires when OTM buffer < 5%
- [ ] ATM Shield buyback uses 10 reprice attempts (not 4)
- [ ] Premium listener circuit breaker wakes heartbeat in < 2 seconds
- [ ] CB_NEAR_ITM executes emergency reduce immediately (no heartbeat wait)
- [ ] Session PAUSED: monitor pauses, listener still runs (positions still protected)
- [ ] Stale monitor detected: generation guard stops it
- [ ] Watchdog detects dead monitor: logs, restarts with new generation
- [ ] Watchdog detects stale listener: logs, restarts
- [ ] Session restore on backend restart: reconciles with exchange
- [ ] Concurrent MMM + MMMX: both run independently, use different DBs, different registries
- [ ] Gap risk: hard stop slippage overshoot 5–15% is accepted (tested with gap simulations)
- [ ] Naked position timeout: after 30min naked, force heartbeat + emergency sell retry
- [ ] Multi-shield priority: sort by worst loss first, execute sequentially, recalc margin after each
- [ ] Reserve depletion cascade: reserve allocated sequentially, partial recovery on exhaustion
- [ ] Margin re-check during execution: check before each reprice, switch to market if >85%
- [ ] Margin critical (95%): abort execution, return failure to caller
- [ ] WebSocket watchdog: if no price update >5min, force heartbeat
- [ ] Critical watchdog: if both listener + heartbeat stale >5min, send operator alert
- [ ] CE/PE imbalance monitoring: calculate ratio, alert if >40%, critical if >60%
- [ ] CE/PE imbalance in session state: `ce_lot_balance` dict shows `imbalance_pct`
- [ ] Hedge capacity threshold (Q51): Tr1–Tr4 NO hedges, Tr5+ activate hedges (50% threshold)
- [ ] Hedge execution timing (Tr5+): 15 min after Tr5 deployment, H-Tr5 buys protective calls/puts
- [ ] Hedge skip for early tranches: Tr1–Tr4 deployed, Telegram: "Below 50% threshold—hedging deferred"
- [ ] Hedge distance configurable on WebUI: user sets %, hot-reload works (Tr5+ only)
- [ ] Multiple hedges simultaneous (Tr5+): H-Tr5 through H-Tr10 all active, H-Tr1–H-Tr4 never created
- [ ] Hedge persists after tranche close: Tr5 closed, H-Tr5 remains open (Tr1–Tr4 never had hedges)
- [ ] Hedge persists after hard stop: hard stop hits, closes shorts, H-Tr5-H-Tr10 orphaned but alive
- [ ] Hedge cost from margin (Tr5+): only H-Tr5+ consume margin, Tr1–Tr4 have zero hedge cost
- [ ] Hedge cost NOT in hard stop: hard stop = 2.0 × shorts premium only (all tranches)
- [ ] Hedge strikes static: don't move when parent tranche repositioned by shield (Tr5+)
- [ ] Margin consumed by hedges (Tr5+): each hedge pair uses margin (long positions)
- [ ] Dashboard shows hedges separately: linked by parent_tranche_id (H-Tr5+ only)
- [ ] Telegram alerts on hedge execution (Tr5+): cost, strikes, status updates
- [ ] Whipsaw detection: oscillating shields within 30-min window increment score
- [ ] Whipsaw CAUTION (score 2): deployment triggers widened from 2% to 3%
- [ ] Whipsaw RESTRICT (score 3): deployment triggers widened to 4%, lot size halved (10→5)
- [ ] Whipsaw COOLDOWN (score 4+): deployments skipped for 1 hour
- [ ] Whipsaw score decay: decreases by 1 per heartbeat interval with no new whipsaws
- [ ] Whipsaw cooldown expiry: score reduces by 2 when cooldown interval expires
- [ ] Whipsaw ATM Shield still fires: protection is never blocked by whipsaw score
- [ ] Whipsaw hard stop still fires: protection is never blocked by whipsaw score
- [ ] Whipsaw Telegram alerts: sent at CAUTION, RESTRICT, COOLDOWN levels + on recovery
- [ ] Whipsaw parameters hot-reloadable: can adjust window, thresholds, decay rate live
- [ ] Whipsaw state persistence: score and timestamps saved/restored on session pause/resume

---

# SECTION 10: FAULT TOLERANCE & RECOVERY

## API Failure Handling (Q22)

When the exchange API becomes unreachable (whitelisting issue, network, exchange downtime):

```
1. Telegram alert: "API failure detected — bot paused. Positions are open. Resolve connectivity."
2. Monitor enters PAUSED mode — no new orders placed.
3. Premium Listener stays active (WebSocket data still flows if market data feed is separate).
4. Bot retries API on every heartbeat cycle.
5. When API resumes: run a FULL heartbeat immediately.
   → Load fresh session, evaluate all conditions, apply any pending protection rules.
   → Do NOT assume conditions are the same as before the failure.
```

**Critical:** The bot never assumes API failure = safe to do nothing. When API resumes, the first action is always a full beat — market may have moved significantly during outage.

## Partial Position Close Handling (Q23)

When a close or reduce order is only partially filled (e.g., exchange fills 6 of 10 lots):

```
1. Reconciliation system records: order_id → lots_filled vs lots_requested
2. Remaining unfilled lots are tracked as a pending close.
3. On every subsequent beat, reconciliation checks: is the position still partially open?
4. Retries the remaining fill (smart_execute on residual size).
5. If market has moved against remaining lots → applies delta gate logic to residual too.
```

**This uses the same reconciliation architecture as the MMM algo** (`mmmx_reconciler.py` mirrors MMM's reconciliation system). Every placed order is mapped by `order_id` + `_pos_id`. The system never considers a close "done" until the exchange confirms full fill.

## Duplicate Order Prevention After Crash (Q24)

**Same mechanism as MMM algo — deterministic `client_order_id` (G8):**

```
client_order_id = hash(session_id + tranche_id + side + action_type + timestamp_bucket)
```

Before placing any order:
1. Check exchange for pending orders matching this `client_order_id`.
2. If already pending: skip — do NOT place duplicate.
3. If filled: record fill, update state, skip new order.

**`_being_closed` guard (180s TTL):** Each position has a `_being_closed` flag. If set and not expired, new close orders are blocked. On session restore, guard is checked and expired guards are cleared before resuming.

## System Restart / Power Loss Recovery (Q25)

**On any restart (power loss, crash, manual stop):**

```
1. Bot starts in PAUSED state automatically.
   → Monitor thread does NOT start.
   → No orders placed.
   → Telegram: "MMMX started in PAUSED state. Manual reconciliation required."

2. Operator opens the MMMX dashboard.
3. Operator clicks "Reconcile" button.
4. System runs reconcile_with_exchange():
   → Loads session from local DB
   → Fetches all open positions from exchange API
   → Compares: DB state vs exchange reality
   → Reports mismatches (positions in DB not on exchange, or vice versa)
   → Operator reviews and confirms

5. After reconciliation confirmed: operator clicks "Resume"
   → Monitor starts with new generation
   → Runs full beat immediately
   → Normal operation resumes
```

**Key invariant:** The system NEVER auto-resumes after a restart. The operator always controls the resume decision after verifying positions match.

---

# SECTION 11: GAPS & OPEN QUESTIONS

## Confirmed Gaps (Not Yet Resolved in Code)

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| **G1** | No executor module | P0 | ✅ Resolved: `mmmx_executor.py` + smart_execute() |
| **G2** | No circuit breaker | P0 | ✅ Resolved: `mmmx_circuit_breaker.py` + Tier-0 listeners |
| **G3** | No session restore on restart | P0 | ✅ Resolved: `init_mmmx()` + reconciliation |
| **G4** | No watchdog | P0 | ✅ Resolved: `mmmx_watchdog.py` |
| **G5** | No generation guard | P0 | ✅ Resolved: 3-layer guard in monitor |
| **G6** | No margin awareness | P1 | ✅ Resolved: executor pre-check + guardian |
| **G7** | No Telegram alerts | P1 | ✅ Resolved: `mmmx_telegram.py` |
| **G8** | No order dedup | P1 | ✅ Resolved: deterministic client_order_id |
| **G9** | No reconciliation | P1 | ✅ Resolved: `reconcile_with_exchange()` in initializer |
| **G10** | No constants | P1 | ✅ Resolved: `mmmx_constants.py` |
| **G11** | No chain service ref | P2 | ✅ Resolved: uses `OptionsChainService` (read-only) |
| **G12** | No DVOL source | P2 | ✅ Resolved: uses `patience_iv.py` (read-only) |
| **G13** | No naked recovery path | P2 | ✅ Resolved: PARTIAL_ENTRY + retry endpoint |
| **G14** | No position model update | P2 | ✅ Resolved: tranche list + UUIDs |
| **G15** | No audit trail | P2 | ✅ Resolved: `mmmx_audit_log.py` |
| **G16** | No health grading | P2 | ✅ Resolved: health metrics in monitor |
| **G17** | No cross-margin awareness | P2 | ✅ Resolved: executor queries exchange (real utilization) |
| **G18** | No liquidity validation | P2 | ✅ Resolved: `validate_liquidity()` in initializer |
| **G19** | Timezone unspecified | P2 | ✅ Resolved: UTC-only mandate |
| **G20** | No build step | P3 | ✅ Resolved: `npm run build` in build order |
| **G21** | Activity types undefined | P3 | ✅ Resolved: taxonomy defined |
| **G26** | No P&L incomplete guard | P1 | ✅ Resolved: `_pnl_calculation_incomplete` flag |
| **G27** | 24h gap → intraday crash undetected | P0 | ✅ Resolved: `mmmx_premium_listener.py` + Tier-0 CB |
| **G28** | Wrong assumption on directional moves | P0 | ✅ Resolved: reposition logic + delta gates |
| **G29** | Single entry at full size | P0 | ✅ Resolved: tranche deployment model |
| **G30** | Large moves (6%+) deploy only 1 tranche, missing opportunity | P0 | ✅ **NEW (2026-04-05)**: Deployment Eligibility Queue (Solution 1). Captures full move across multiple beats. Queue clears on >0.5% retracement. |
| **G31** | Missed tranches never backfilled | P0 | ✅ **NEW (2026-04-05)**: Queue mechanism ensures backfill happens automatically over next beats. |
| **G32** | Recovery positions unmonitored — ATM Shield blind to reserve lots | P1 | ✅ **NEW (2026-04-05)**: Recovery lots created as sibling tranches (2A, 2B, 2C). Full first-class tranche citizens — ATM Shield, hard stop, delta gate, DTE close, close_all all apply automatically. `tranches_deployed`/`tranches_remaining` NOT incremented. Recovery premiums DO count toward `total_premium_collected`. Max siblings per parent = `atm_shield_max_shifts` (default 3). |
| **G36** | Hard stop trigger ≠ hard ceiling — slippage breach possible | P1 | ✅ **NEW (2026-04-05)**: Gap Risk & Execution Reality. Hard stop is trigger point, accepts 5–15% slippage overshoot during gaps. System guarantees close_all fires immediately, but fills may be worse. User must accept this. |
| **G37** | Naked position can sit indefinitely after sell failure | P1 | ✅ **NEW (2026-04-05)**: Naked Position Timeout. Max 30min naked. At 30min: force heartbeat + emergency sell retry. At 2hr: escalation alert to operator. |
| **G38** | Multi-shield execution: no priority, can stall on margin | P1 | ✅ **NEW (2026-04-05)**: Multi-Shield Execution Order. Sort by worst loss first. Pre-check total margin. Execute sequentially, recalculate after each. If margin would breach: stop, try next beat. |
| **G39** | Reserve depletion cascade: shields can fail silently mid-beat | P1 | ✅ **NEW (2026-04-05)**: Reserve Depletion Cascade. Allocate reserve sequentially across shields. Partial recovery if reserve runs out. Reposition without recovery if exhausted. Degrade gracefully. |
| **G40** | Margin can spike mid-execution, order can breach 80% limit | P1 | ✅ **NEW (2026-04-05)**: Continuous Margin Re-Check During Execution. Check before each reprice. If margin 85%+: switch to market order. If 95%+: abort execution. |
| **G41** | WebSocket stale → undetected P&L movement → heartbeat delay | P1 | ✅ **NEW (2026-04-05)**: Heartbeat Delay Watchdog. If price update stale >5min: force heartbeat. If both listener + heartbeat stale: critical alert. |
| **G42** | CE/PE lot imbalance not monitored (structural risk) | P2 | ✅ **NEW (2026-04-05)**: CE/PE Lot Imbalance Monitoring. Calculate imbalance_pct. Alert if >40%. Alert critical if >60%. Dashboard shows balance. |
| **G43** | No protective spreads for black swan (no definite loss cap) | P0 | ✅ **NEW (2026-04-05)**: Automatic Hedging (Third Safety Layer). Buy protective long calls/puts 15min after each short deployment. Caps definite loss. Hedges persist until all shorts closed, even after hard stop. See Q43–Q60. |
| **G44** | No oscillation protection (whipsaw trap: capital deployed into market noise) | P1 | ✅ **NEW (2026-04-05)**: Whipsaw Guard (Fourth Protection Layer). Detect oscillating shields + oscillating deployments. Four-level graduated response: NORMAL → CAUTION (widen 50%) → RESTRICT (widen 100%, halve lots) → COOLDOWN (pause 1hr). Score decays naturally; protects deployment capital from noise. See Whipsaw Guard section. |

## Open Questions (Require Operator Input Before Final Build)

| # | Question | Current Assumption | Needs Approval |
|---|---|---|---|
| **Q1** | When ATM Shield reserve is exhausted mid-shift, should original lots reposition be attempted anyway (without recovery) or abort entire shift? | ✅ **CONFIRMED**: Reposition anyway, skip recovery. Operator alert sent. | ✓ Confirmed ✅ |
| **Q2** | After 6% move — how many tranches deploy? Are missed tranches tracked? | ✅ **RESOLVED**: Deployment Eligibility Queue (Solution 1). 6% / 2% = 3 tranches eligible, deployed across 3 beats, queue clears on >0.5% retracement. See Section 2. | ✓ Confirmed ✅ |
| **Q3** | If spot moves 2% AND IV spikes 10% in same beat — confirm still only ONE tranche deployed? | Yes, one per beat maximum (but queued tranches continue deploying next beat) | ✓ Confirmed ✅ |
| **Q4** | Profit target: close ALL (all tranches + recovery) or just profitable tranches? | ✅ **CONFIRMED**: Close all (same as hard stop — all tranches + all recovery tranches). | ✓ Confirmed ✅ |
| **Q5** | When Tranche 1 CE is repositioned via ATM Shield, preserve original $100 entry premium for analytics? | Yes, preserved in `shield_history` array | ✓ Confirmed ✅ |
| **Q6** | If both CB_PREMIUM_JUMP and CB_DELTA_BLOWOUT fire same tick, does heartbeat see both or just one? | Both conditions are visible to heartbeat (CB just wakes it; heartbeat makes decision) | ✓ Confirmed ✅ |
| **Q7** | DTE-adaptive CB thresholds: are these correct? (`delta_blowout` 0.45 at >15 DTE, 0.40 at 7–15 DTE) | Yes, tighter as expiry approaches (higher gamma) | ✓ Confirmed ✅ |
| **Q8** | Should ATM Shield check fire on EVERY beat if the condition is true, or only once per position? | Every beat while condition is true (until fixed or reserve exhausted) | ✓ Confirmed ✅ |
| **Q9** | If no OTM strike is available for new deployment or reposition — what happens? | ✅ **RESOLVED**: Hold new tranche deployment. Check every heartbeat for strike availability. Open tranches: protected via normal shield/delta-gate if they approach threshold. Telegram alert. See ATM Shield Constraints table. | ✓ Confirmed ✅ |
| **Q10** | If buyback succeeds but new sell fails — what is system state? What happens next? | ✅ **RESOLVED**: Already defined as Shield Sell Retry Mechanism (Step 3 in ATM Shield). 10 limit reprice attempts × 30s each, then market order fallback. If ALL 11 fail: session PAUSED + NAKED ALERT + Telegram CRITICAL. | ✓ Confirmed ✅ |
| **Q11** | If ATM Shield reserve becomes zero — what parts of shield still execute? What stops? | ✅ **CONFIRMED**: Reposition still executes (original lots moved to fresh OTM strike). Recovery tranche creation is skipped. Telegram alert sent. Already defined in "Reserve accounting" in Step 5. | ✓ Confirmed ✅ |
| **Q14** | After a 6% fall (hypothetically 3 missed tranches) — will system deploy them later? | ✅ **RESOLVED**: Queue mechanism ensures missed tranches ARE deployed over next 2–3 beats (one per beat), but ONLY if market hasn't retraced >0.5%. See Section 2. | ✓ Confirmed ✅ |
| **Q18** | If both listener and heartbeat trigger at same time — which takes priority? | ✅ **RESOLVED**: Heartbeat has priority. Listener detects + wakes; heartbeat decides. Exception: CB_NEAR_ITM executes 50% emergency reduce immediately, then still wakes heartbeat. See Section 4 "Listener vs Heartbeat Priority". | ✓ Confirmed ✅ |
| **Q21** | If hard stop hits DURING ATM Shield execution — what happens? | ✅ **RESOLVED**: Hard stop is non-negotiable. Current atomic step completes (avoids naked position), then next beat catches hard stop and calls close_all. See Hard Stop section. | ✓ Confirmed ✅ |
| **Q22** | If API fails — does bot retry, pause, or continue? | ✅ **RESOLVED**: Bot pauses, sends Telegram alert, retries each heartbeat. When API resumes: runs full beat immediately. See Section 10. | ✓ Confirmed ✅ |
| **Q23** | If position partially closes — how is remaining handled? | ✅ **RESOLVED**: Reconciliation system tracks partial fills by order_id + _pos_id. Retries residual on subsequent beats. Same architecture as MMM algo. See Section 10. | ✓ Confirmed ✅ |
| **Q24** | If monitor crashes mid-execution — can duplicate orders happen? | ✅ **RESOLVED**: Deterministic client_order_id dedup (G8) + _being_closed guard (180s TTL) prevent duplicates. Same method as MMM algo reconciliation. See Section 10. | ✓ Confirmed ✅ |
| **Q25** | If system restarts — how does it rebuild state? | ✅ **RESOLVED**: Bot starts in PAUSED state. Operator uses Reconcile button to compare DB vs exchange. Operator confirms, then clicks Resume. Monitor starts with new generation. See Section 10. | ✓ Confirmed ✅ |
| **Q26** | Core objective of deployment — premium maximization or delta balancing? | ✅ **RESOLVED**: Theta capture through gradual capital commitment. Not delta directional. Deploy on confirmed moves to collect fat premiums. See Section 1. | ✓ Confirmed ✅ |
| **Q27** | Core objective of ATM Shield — survival or profit recovery? | ✅ **RESOLVED**: Survival — stay OTM, never fight the market. Insurance company model: revoke dangerous insurance, sell new safer insurance. See Section 1. | ✓ Confirmed ✅ |
| **Q28** | Can deployment and protection objectives conflict? Who wins? | ✅ **RESOLVED**: Protection ALWAYS wins. Absolute priority order: hard stop → DTE → shield → delta gates → CBs → deployment. See Section 1. | ✓ Confirmed ✅ |
| **Q29** | Vol crush scenario (IV spikes then collapses) — should system auto-take partial profits? | ✅ **CONFIRMED**: No automation. Manual operator decision via Per-Tranche Profit Booking feature. Operator selects individual tranches and sets profit targets (10%, 20%, 30%, 50%) independently per tranche. Each tranche evaluated separately (not portfolio-level). | ✓ Confirmed ✅ |
| **Q30** | Slow trend protection (1% moves every 3–4 hours, accumulates to 8% over 48h) — how to prevent chasing? | ✅ **CONFIRMED**: Deployment frequency gate. Max 2 deployments per 24h (hot-reloadable). Shield continues to work as designed. Prevents transaction cost bleed. | ✓ Confirmed ✅ |
| **Q31** | Over-repositioning risk (shield fires repeatedly on oscillating market) — is 3-shift cap enough? | ✅ **CONFIRMED**: Yes, as designed. 3 shifts = max 3 sibling recovery tranches (2A, 2B, 2C). Transaction costs + liquidity constraints make 3 sufficient. | ✓ Confirmed ✅ |
| **Q32** | All tranches deployed, reserve partially used — what's the defensive posture? | ✅ **RESOLVED**: Operator can use Profit Booking to close winners → frees deployment capacity → creates space for fresh tranches OR defensive reduction. User controls via hot-reload profit targets. | ✓ Confirmed ✅ |
| **Q33** | Correlated risk (black swan: both CE and PE deltas spike together) — portfolio-level protection? | ✅ **CONFIRMED**: Portfolio-level hard stop exists. Closes ALL tranches + ALL recovery tranches on portfolio P&L breach. No partial hedges. Captures correlated blowup regardless of which side fails first. See Hard Stop section. | ✓ Confirmed ✅ |
| **Q34** | Early profit capture (if you capture 50% premium in 5 days, why wait 25 more?) — acceleration logic? | ✅ **RESOLVED**: Profit Booking feature handles this. Operator can close any tranche at any % target. Removes emotion from timing. Frees capital for new deployment. | ✓ Confirmed ✅ |
| **Q35** | Psychology failsafe (emotions + panic override) — allow manual overrides? | ✅ **CONFIRMED**: NO. Hard stop is law. No override possible. Operator can adjust hard_stop_multiplier BEFORE session starts, or pause deployment, or stop session gracefully. But once running, hard stop is absolute and non-negotiable. No emotions. | ✓ Confirmed ✅ |
| **Q36** | Gap risk: hard stop is guarantee or just trigger? | ✅ **RESOLVED**: Hard stop is TRIGGER POINT only. Slippage overshoot 5–15% is accepted. System guarantees close_all fires immediately, but fills may be worse. Design is right; user must accept slippage reality. See G36. | ✓ Confirmed ✅ |
| **Q37** | Naked position from sell failure — how long can it sit? | ✅ **RESOLVED**: Max 30 minutes. At 30min: force heartbeat + emergency sell retry. At 2hr: escalation alert to operator. System does NOT let you sit naked indefinitely. See G37. | ✓ Confirmed ✅ |
| **Q38** | Multiple shields same beat — execution order? Margin stacking? | ✅ **RESOLVED**: Sort by worst loss first. Pre-check total margin. Execute sequentially, recalculate margin after each shield. If margin would breach: stop, try remaining shields next beat. See G38. | ✓ Confirmed ✅ |
| **Q39** | Recovery cascade reserve depletion — what happens? | ✅ **RESOLVED**: Reserve allocated sequentially across shields. If exhausted mid-cascade: partial recovery or zero recovery (reposition only). Degrade gracefully, no silent failures. See G39. | ✓ Confirmed ✅ |
| **Q40** | Margin can spike during execution — re-check or ignore? | ✅ **RESOLVED**: Continuous re-check before each reprice. If margin >85%: switch to market order. If >95%: abort execution. Prevent breaching margin limits mid-execution. See G40. | ✓ Confirmed ✅ |
| **Q41** | WebSocket stale (5min no price update) — forced heartbeat? | ✅ **RESOLVED**: Yes. If price update stale >5min: force heartbeat immediately. If both listener + heartbeat stale >5min: critical alert to operator. Detect dead monitor. See G41. | ✓ Confirmed ✅ |
| **Q42** | CE/PE lot imbalance — monitored or ignored? | ✅ **RESOLVED**: Monitored continuously. Calculate imbalance_pct. Alert if >40%. Critical alert if >60%. Show in dashboard + Telegram. Not a hard stop, but visibility + awareness. See G42. | ✓ Confirmed ✅ |
| **Q43** | Third safety layer: buy protective spreads after deployment? | ✅ **CONFIRMED**: YES. Automatic Hedge Buying (insurance). Buy long calls/puts 15min after each tranche deployment. User defines hedge distance % on WebUI (default 20%, hot-reload). Caps definite loss in black swan. See G43, Automatic Hedging section. | ✓ Confirmed ✅ |
| **Q44** | Hedge closing: when do hedges close? | ✅ **CONFIRMED**: NEVER automatically closed by bot. Hedges persist until ALL sold positions (all tranches) completely closed. Even if tranche closed via profit booking, hedge remains. Even if hard stop hits, hedges survive (orphaned but alive). Close only when session ends or operator manually closes. | ✓ Confirmed ✅ |
| **Q45** | Hedge cost: margin or capital? | ✅ **CONFIRMED**: Paid from margin (capital cost of doing business). NOT deducted from tranche premium_collected. Hedge cost is operational expense, separate accounting. Hard stop based on shorts only, not hedges. | ✓ Confirmed ✅ |
| **Q46** | Multiple hedges simultaneous? | ✅ **CONFIRMED**: YES. Each tranche gets its own hedge (H-Tr1 through H-Tr10). All active simultaneously. Each hedge pair has independent strikes + premium + P&L. | ✓ Confirmed ✅ |
| **Q47** | Hedges after hard stop: what happens? | ✅ **CONFIRMED**: Hedges remain in system. When hard stop closes all shorts, hedges stay open (orphaned). No automatic close. Decay to $0 at expiry. This is acceptable (insurance that expired). Session status = COMPLETE, hedges are remnants. | ✓ Confirmed ✅ |
| **Q48** | Hedge strikes static or move with shield? | ✅ **CONFIRMED**: Static. Hedges don't move when tranche gets repositioned by shield. If Tr1 repositioned → Tr1A created, but H-Tr1 still @ original strikes (84K/56K). H-Tr1 becomes "displaced" but remains alive. System logs displacement. | ✓ Confirmed ✅ |
| **Q49** | Hedge margin impact: blocks deployments? | ✅ **CONFIRMED**: YES. Hedges consume margin (long positions need margin). If hedges + shorts exceed margin, next deployment blocked. User controls via hedge_distance_pct (lower % = cheaper hedge = more margin available). Balance needed between protection + deployment capacity. | ✓ Confirmed ✅ |
| **Q50** | Hedge timing: 15 minutes after deployment always? | ✅ **CONFIRMED**: YES. 15 minutes fixed (hedge_execution_delay_minutes = 15, hot-reloadable). After tranche deployment completes, schedule hedge execution for 15min later (separate heartbeat). Buy hedges at that time using live strikes. | ✓ Confirmed ✅ |

## Design Assumptions to Confirm

| Assumption | Current Design | Needs Approval |
|---|---|---|
| Initial entry always manual (operator clicks "Deploy") | Yes, no auto-entry on session create | ✓ Confirmed ✅ |
| Tranche 1 entry size fixed at 10% | Yes, `tranche_pct` not user-configurable per deployment | ✓ Confirmed ✅ |
| ATM Shield recovery is REQUIRED (not optional) | Yes, critical for loss offsetting | ✓ Confirmed ✅ |
| Hard stop multiplier hot-reloadable | Yes, operator can adjust live | ✓ Confirmed ✅ |
| `close_at_dte=7` is absolutely hard-enforced | Yes, config rejects anything < 7 | ✓ Confirmed ✅ |
| Multiple tranches open simultaneously is correct | Yes, old tranches collect theta deeper OTM | ✓ Confirmed ✅ |
| Premium listener runs even when heartbeat is paused | Yes, PAUSED means heartbeat pauses, listener stays active | ✓ Confirmed ✅ |
| Fairness gate (BS vs mid-price check) for deployments | Yes, enabled by default. Hot-reloadable toggle on WebUI so operator can disable if liquidity is high | ✓ Confirmed ✅ |
| Profit booking (per-tranche selective close) | Yes, operator can manually close individual tranches at 10%/20%/30%/50% targets. Per-tranche granularity (not portfolio-level). Hot-reloadable. Frees deployment capacity. | ✓ Confirmed ✅ |
| ATM Shield max shifts = 3 is sufficient | Yes, as designed (Q31). Transaction costs prevent more. | ✓ Confirmed ✅ |
| Max deployments per day gate | Yes, default 2 to prevent chasing slow trends. Hot-reloadable. (Q30) | ✓ Confirmed ✅ |
| Portfolio hard stop prevents correlated risk | Yes, portfolio-level P&L check. Closes ALL tranches + recovery on breach. No partial hedges. (Q33) | ✓ Confirmed ✅ |
| Operator override of hard stop allowed | NO. Hard stop is law. No exceptions, no emotions. Operator can adjust multiplier before session start only. (Q35) | ✓ Confirmed ✅ |
| Vol crush profit-taking | Manual operator decision (D). No automatic profit target logic; operator uses profit booking feature. (Q29) | ✓ Confirmed ✅ |

## Known Limitations (Post-MVP Roadmap)

| Feature | Status | Why Deferred |
|---|---|---|
| Strike shift module | ❌ Not in v1 | Rolls replace shifts; unnecessary for monthly |
| Close-at-threshold | ❌ Not in v1 | DTE-based exit sufficient for MVP |
| Regime controls (vol/gamma/trend) | ❌ Not in v1 | Less relevant for weekly/daily cadence |
| Perp futures hedge | ❌ Not in v1 | Adds complexity; rolls manage delta |
| Event calendar awareness | ❌ Not in v1 | Deferred to v2 |
| IV-RV realized spread tracking | ❌ Not in v1 | v2 analytics feature |
| Concentration risk per strike | ❌ Not in v1 | Small positions don't require this yet |
| Portfolio net vega hard limit | ❌ Not in v1 | v2 extension (currently only monitors) |
| Daily/rolling 24h loss limit | ❌ Not in v1 | Hard stop covers MVP needs |
| Execution TWAP/iceberg slicing | ❌ Not in v1 | Smart execute sufficient for 10–30 lot orders |

---

# QUICK REFERENCE

## Key Files by Function

| Function | Primary File | Supporting Files |
|---|---|---|
| Deployment decision | `mmmx_trigger.py` | `mmmx_engine.py` |
| Strike selection | `mmmx_initializer.py` | (live exchange API) |
| Order execution | `mmmx_executor.py` | `mmmx_circuit_breaker.py` |
| ATM protection | `mmmx_atm_shield.py` | `mmmx_engine.py`, `mmmx_executor.py` |
| Hard stop check | `mmmx_monitor.py` | `mmmx_engine.py` |
| Real-time detection | `mmmx_premium_listener.py` | `mmmx_circuit_breaker.py` |
| Session restore | `__init__.py` | `mmmx_initializer.py` |
| Monitoring | `mmmx_monitor.py` + `mmmx_premium_listener.py` | `mmmx_watchdog.py` |

## Key Thresholds

| Parameter | Default | Hot-Reloadable | Enforced Min/Max |
|---|---|---|---|
| close_at_dte | 7 | Yes | MIN 7 (non-negotiable) |
| otm_distance_pct | 15% | Yes | 5–30% |
| hard_stop_multiplier | 2.0 | Yes | 1.0–5.0 |
| atm_protect_threshold | 5% | Yes | 1–10% |
| atm_shield_max_shifts | 3 | Yes | 1–10 |
| tranche_deploy_move_pct | 2% | Yes | 0.5–10% |
| adjustment_interval_hours | 1 | Yes | 0.5–24 |
| emergency_delta | 0.70 | Yes | 0.60–0.95 |
| whipsaw_window_mins | 30 | Yes | 10–120 |
| whipsaw_spot_move_pct | 0.3% | Yes | 0.1–1.0% |
| whipsaw_caution_score | 2 | Yes | 1–5 |
| whipsaw_restrict_score | 3 | Yes | 2–6 |
| whipsaw_cooldown_score | 4 | Yes | 3–7 |

## Scenarios (Decision Tree)

**BTC drops 6% in 1 hour:**
- Premium Listener CB fires within 1–2 seconds
- Wakes heartbeat immediately
- Heartbeat evaluates threatened side (PE) delta
- If delta 0.35–0.54: REPOSITION (roll both sides, collect elevated IV)
- If delta 0.55–0.69: REDUCE_THEN_ROLL (reduce threatened first, then reposition)
- If delta >= 0.70: CLOSE_ALL (near ITM, unmanageable)
- Result: **Never blindly closes all; always applies delta gates**

**Market retraces within 1 hour:**
- Old tranches go back to original OTM distance (no action)
- IV subsides (deployment NOT triggered)
- Capital preserved for real opportunity
- Result: **Saves capital for confirmed moves**

**ATM Shield fires:**
- Buys back endangered position (5 min max with reprice loop)
- Sells new position at fresh strike (OTM protected)
- Sells recovery lots from 30-lot reserve
- If reserve exhausted: reposition still happens, Telegram alert
- Result: **Position never approaches ATM; loss is limited and recoverable**

**Hard stop is hit:**
- Closes ALL tranches + all recovery lots immediately
- Session status: COMPLETE
- Telegram: CRITICAL
- Result: **Absolute protection, no exceptions**

---

**Document Complete.**  
**Last Updated:** 2026-04-05  
**Status:** Ready for implementation — all Q1–Q50 resolved + Third Safety Layer Hedging  
**Approval:** All open questions confirmed ✅ — Gap fixes (G36–G42), Automatic Hedging (G43, Q43–Q50) all locked down. ZERO outstanding gaps. **THREE protective layers guaranteed:**
  1. **Hard Stop** (portfolio-level absolute ceiling)
  2. **ATM Shield** (per-position reposition before ITM)
  3. **Automatic Hedging** (protective spreads, caps definite loss, persists to expiry)

Ready for MVP build and live deployment.
