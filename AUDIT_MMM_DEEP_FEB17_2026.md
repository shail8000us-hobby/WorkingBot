# MMM Deep Audit Report — February 17, 2026

## Sessions Analyzed

| Session | Duration | Adj | Rev | Shifts | Close@5 | Net P&L | CE Final | PE Final |
|---------|----------|-----|-----|--------|---------|---------|----------|----------|
| mmm_019d87 | 77 min (10:28–11:45 UTC) | 9 | 12 | 3 | 9 | **+$1.44** | 1 lot @67800 | 5 lots @67800 |
| mmm_09cde2 | 3h 4m (08:42–11:46 UTC) | 28 | 24 | 4 | 16 | **+$17.41** | 60 lots @67800 | 36 lots (16@68000 + 20 frozen@67800) |
| mmm_f48816 | 19h+ (16 Feb 17:13–running) | 10 | — | — | 0 | +$1.12 | Data integrity issues |

---

## PART 1: LOGIC AND CALCULATION FLAWS

### FLAW 1 (CRITICAL): Frozen Position Loss — Double-Counting Bug

**Spec Reference**: §5.2 Case A, §6.2

**The Problem**: The standard loss formula calculates frozen position losses using `(current_premium - entry_premium)`, which is the TOTAL loss since the position was opened. But the active position loss uses `(premium_now - trigger_snapshot)`, which is INCREMENTAL loss since the last adjustment.

After an adjustment hedges a frozen position's loss:
- Active position trigger ratchets up → next interval only counts NEW loss above trigger (correct)
- Frozen position uses entry_premium → next interval counts the SAME total loss again (wrong)

**Example trace from mmm_09cde2**:
1. CE frozen at 68000 with entry=$70, current=$90 → loss = 20 per lot
2. Algo hedges by selling PE → collects premium to cover the $20 loss
3. Next heartbeat: CE frozen still at $90 → loss = (90-70) = 20 per lot AGAIN
4. Algo hedges AGAIN for the same $20 that was already covered
5. Net effect: sells 2× the PE lots actually needed

**Evidence**: mmm_09cde2 went from 1 CE lot to 60 CE lots. Adjustment #20 sold `37 lots` in a single trade. Adjustment #21 sold `35 lots`. This explosive growth is consistent with repeated re-hedging of frozen losses.

**§6.2 says**: "Also snapshot any other strikes with active positions: for each strike with open positions: trigger_snapshot[strike] = fetch_premium(strike)"

**Implementation**: `update_trigger_snapshots()` in mmm_trigger.py only updates the active CE and PE strikes. It ignores frozen position strikes entirely. If implemented per spec, frozen losses would also be incremental.

**Impact**: Over-hedging → exponential position growth → amplified lot counts → magnified risk on reversals.

---

### FLAW 2 (HIGH): No Per-Adjustment Lot Cap

**Spec Reference**: §5.4

**The Spec Says**: `lots_to_sell = min(lots_to_sell, max_adjustment_lots)` — there should be a per-adjustment cap.

**Implementation**: `calculate_lots_to_sell()` in mmm_engine.py only enforces `max_lots_per_side` (total cap), not a per-adjustment cap. A single adjustment can sell unlimited lots up to the total cap.

**Evidence**: mmm_09cde2 adjustment #17 sold 38 lots, #18 sold 22 lots, #20 sold 37 lots, #21 sold 35 lots — all in single adjustments.

**Impact**: A single bad heartbeat can commit the algo to a massive position in one shot, with no opportunity to validate the decision.

---

### FLAW 3 (HIGH): Positive Feedback Amplification Loop

**Not addressed in spec at all.**

The algo has a structural amplification loop:

```
More lots → bigger loss per premium move → more hedge lots needed →
even MORE lots → even BIGGER loss per move → ...
```

mmm_09cde2 demonstrates this perfectly:
- Adj #0: 6 lots (hedging 1-lot CE entry)
- Adj #11: 9 lots (hedging growing positions)
- Adj #17: 38 lots (shift — hedging ~40 lots of accumulated CE)
- Adj #20: 37 lots (hedging ~100 CE lots)
- Adj #21: 35 lots (reversal — hedging the hedge)

Each cycle of adjustments INCREASES total lots, which makes the NEXT cycle's adjustments larger. This is compounded by Flaw 1 (double-counting frozen losses).

**Missing**: Position growth rate limiter, per-adjustment cap, or circuit breaker.

---

### FLAW 4 (MEDIUM): Reversal Count Inflation

**Spec Reference**: §9

`record_reversal()` is called on every reversal DETECTION, including when the adjustment is skipped (profitable). The `reversal_count` becomes misleading.

**Evidence**: mmm_019d87 shows 12 reversals but only 9 adjustments. Multiple reversals recorded at the same `adjustment_count_at` value (e.g., 4 reversal entries all at adj #9). These are noise oscillations that were correctly skipped but inflated the counter.

**Impact**: Dashboard shows artificially high reversal count, obscuring the actual number of reversal-triggered adjustments.

---

### FLAW 5 (MEDIUM): Entry Fill Quality Not Validated

**Spec Reference**: §3

mmm_019d87 requested `desired_ce_premium=100`, `desired_pe_premium=100`. Actual fills: CE=37.0, PE=34.5. That's 63-65% below the requested premium. The strike finder found strikes with premiums far below target, and the auto-proceed timer accepted them.

mmm_09cde2 also requested 100/100. Got CE=111.0, PE=82.5 — closer but PE was 17.5% below target.

**Impact**: Starting with premiums much lower than intended means less buffer, smaller initial hedge value, and more aggressive early adjustments needed.

---

### FLAW 6 (LOW): Fee Tracking Not Implemented

**Spec Reference**: §15.8

Both sessions show `total_fees: 0.0`. The spec explicitly says "Account for fees in P&L tracking." With 28 adjustments + 16 close-at-5 = 44 orders in mmm_09cde2, fee impact is material.

**Impact**: Reported P&L is overstated. For Delta Exchange India at 0.05% taker, 44 orders with average ~$80 premium and varying lot sizes would incur meaningful fees.

---

### FLAW 7 (LOW): Margin Not Pre-Checked via Exchange API

**Spec Reference**: §13.7

The spec says: "Before every sell order: available_margin = fetch_available_margin()". The implementation uses position count as a proxy only.

**Impact**: The algo could attempt orders that get rejected by the exchange due to insufficient margin, which would be caught as execution errors but not pre-emptively prevented.

---

## PART 2: SESSION-SPECIFIC ANALYSIS

### mmm_019d87 — The Whipsaw Session

**Timeline**: 77 minutes active, 60s heartbeat, 1-lot entry.

**Configuration Issues**:
- `whipsaw_limit=30`: Effectively disabled (spec default: 3). With 12 reversals in 77 minutes, whipsaw detection at 3 would have paused the algo after the 3rd alternating adjustment and prevented 6+ unnecessary adjustments.
- `cooldown_on_reversal=False`: Disabled the noise filter. The rapid PE→CE→PE→CE pattern between 10:47-10:59 (3 reversals in 12 minutes) is textbook noise that cooldown would filter.
- `min_trigger_move=3`: Appropriate for this premium range but combined with disabled cooldown/whipsaw, it let noise through.

**Positive Observations**:
- Close-at-5 worked correctly: all 9 original and adjustment positions at old strikes were closed as premium decayed.
- Final P&L was positive ($1.44 on $0.07 initial premium = ~20× return on premium basis).
- Strike shifts worked: CE migrated 68200→68000→67800, PE migrated 67600→67800.
- Auto-close at expiry executed properly.

**What Went Wrong**:
- 12 reversals in 9 adjustments = the algo was chasing oscillations.
- Final position: 1 CE + 5 PE = 6 lots from 2-lot entry (3× growth).
- Growth was contained only because the 1-lot initial size and short duration limited the amplification loop.

---

### mmm_09cde2 — The Amplification Session

**Timeline**: 3 hours, 60s heartbeat, 1-lot entry, more aggressive params.

**Configuration Issues**:
- `min_trigger_move=2`: Too sensitive. BTC options oscillate 5-10 on normal market noise. A trigger of 2 fires on almost every heartbeat.
- `max_lots_per_side=200`: Too generous. Allowed CE to accumulate 60 lots (30% of cap) from a 1-lot entry. A cap of 20-30 would have contained growth.
- `whipsaw_limit=30`: Again effectively disabled.
- `cooldown_on_reversal=False`: Disabled.

**Lot Growth Timeline**:
| Time | CE Lots | PE Lots | Event |
|------|---------|---------|-------|
| 08:42 | 1 | 1 | Entry |
| 08:47 | 1 | 7 | +6 PE (first adj) |
| 09:13 | 10 | 11 | CE growing from reversals |
| 09:19 | 11 (shifted) | 16 | CE shifts to 68200 |
| 09:54 | 43 | 16 | CE accumulates at 68200 via reversals |
| 10:17 | 38 (shifted) | 16 | CE shifts to 68000 |
| 10:37 | 103 | 16 | +37 lots in ONE adj (#20) |
| 10:40 | 138 | 16 | +35 lots (reversal adj #21) |
| 10:46 | ~140+ | 16 | Peak CE lots (before close-at-5 cleanup) |
| 11:26 | 43 (shifted) | 36 | CE shifts again, cleaned prior |
| 11:46 | 60 | 36 | Final state |

The position grew **60× from entry** on CE side and **36× on PE side**.

**Positive Observations**:
- Despite the explosive growth, the session ended profitable: $17.41 net ($17.59 realized, -$0.18 unrealized).
- Close-at-5 closed 16 positions, recovering premium on decaying options.
- The realized P&L ($17.59) was overwhelmingly from close-at-5 events — options sold at $60-110 and bought back at $5.
- The system survived 28 adjustments, 24 reversals, 4 shifts without crashing.

**What Went Wrong**:
- The amplification loop drove CE from 1 to 140+ lots before close-at-5 cleaned up.
- Between 10:28 and 10:46 (18 minutes): 4 adjustments sold 22+6+37+35 = 100 CE lots. That's a massive burst.
- The position asymmetry hit ~9:1 (CE:PE) but the whipsaw limit of 30 prevented it from triggering an alert.

---

### mmm_f48816 — The Long-Running Session

**Duration**: 19+ hours, 120s interval, 1-lot entry, min_trigger_move=30.

**Data Integrity Issue**: Core fields are `None` — `total_adjustments`, `total_reversals`, `total_shifts`, `heartbeat_count`, CE/PE `active_lots`, `total_lots` all show `None`. The `adjustment_history` shows entries with empty `lots` and `$0.00` premium. This session was likely created with an older data schema before certain fields were added, and the missing fields were never backfilled.

**Impact**: Cannot perform full analysis on this session. The session IS running and has 10 adjustment entries and $1.12 unrealized P&L, but the position details are not available for audit.

---

## PART 3: WHAT'S MISSING FOR INSTITUTIONAL GRADE

### 3.1 — Trade Data Persistence (CRITICAL)

Currently: NO persistent trade record exists. Session data is stored in SQLite but individual orders/fills are embedded in session JSON. When a session stops, the only record is the final state blob. There is no searchable trade journal.

**What's needed**:

A `mmm_trades` table:
```
trade_id        INTEGER PRIMARY KEY
session_id      TEXT
timestamp       TEXT
order_type      TEXT    -- 'entry'|'adjustment'|'close_at_5'|'shift'|'auto_close'
side            TEXT    -- 'CE'|'PE'
strike          REAL
lots            INTEGER
direction       TEXT    -- 'sell'|'buy'
entry_premium   REAL
fill_premium    REAL
slippage        REAL    -- fill vs mark price
fees            REAL
latency_ms      INTEGER -- API round trip
reason          TEXT    -- 'standard_adj'|'first_reversal'|'shift_adj'|'close_at_5'|'max_loss'
loss_to_cover   REAL    -- what loss triggered this trade
premium_collected REAL
```

Plus a `mmm_snapshots` table for per-heartbeat state:
```
snapshot_id     INTEGER PRIMARY KEY
session_id      TEXT
heartbeat_num   INTEGER
timestamp       TEXT
ce_premium      REAL
pe_premium      REAL
ce_trigger      REAL
pe_trigger      REAL
ce_active_lots  INTEGER
pe_active_lots  INTEGER
ce_total_lots   INTEGER
pe_total_lots   INTEGER
unrealized_pnl  REAL
realized_pnl    REAL
net_pnl         REAL
spot_price      REAL
outcome         TEXT    -- 'none'|'ce_triggered'|'pe_triggered'|'both'
```

This enables: backtesting, parameter optimization, audit trails, regulatory compliance, and strategy attribution.

---

### 3.2 — Anti-Amplification Circuit Breaker

**Missing entirely from spec and implementation.**

Proposed rules:
1. **Per-adjustment lot cap**: No single adjustment sells more than `max(5, current_total_lots * 0.25)` lots. Forces gradual position building.
2. **Growth rate alert**: If total_lots grows >3× from entry within any 30-minute window, PAUSE and alert.
3. **Exponential backoff on reversals**: After 3 consecutive reversals, double min_trigger_move temporarily. After 5, pause.
4. **Net exposure cap**: `|CE_total - PE_total| / max(CE_total, PE_total) <= 0.8`. Prevents extreme one-sided exposure.

---

### 3.3 — Volatility Regime Detection

**Missing entirely.**

The algo treats a trending market (consistent aggressor) and an oscillating market (rapid reversals) identically. These require opposite strategies:
- **Trending**: Standard adjustments work well. Low trigger move is fine.
- **Oscillating**: Every adjustment is reversed, creating lot buildup. Should WIDEN triggers and INCREASE interval.

Proposed: Track the standard deviation of premium changes over the last N heartbeats. If `stdev > 2 * min_trigger_move`, auto-widen triggers to `stdev * 1.5`. This adapts to current market conditions rather than using static parameters.

---

### 3.4 — Greeks-Based Decision Making

**Missing entirely.**

Currently: decisions based purely on premium levels (trigger snapshots vs current premium).

What institutional grade needs:
- **Delta**: Tells you directional exposure. If combined delta is -0.5, you're effectively short 0.5 BTC. Should cap delta exposure.
- **Gamma**: Tells you how fast delta changes. High gamma near ATM = more volatile P&L = widen triggers.
- **Vega**: Tells you IV exposure. If vega is high, a vol spike hurts both sides simultaneously (§8 scenario).
- **Theta**: The entire strategy's profit source. Track daily theta decay rate to estimate expected income.

Delta Exchange India's API provides mark price, bid, ask. Greeks can be computed from Black-Scholes or fetched if available.

---

### 3.5 — Dynamic Parameter Tuning

**Missing entirely.**

Instead of static `min_trigger_move=3` or `=30`, use adaptive parameters:

```
realized_vol = stdev(premium_changes, last_10_heartbeats)
effective_trigger = max(base_trigger, realized_vol * 0.5)
```

This auto-adjusts to market conditions without manual intervention.

---

### 3.6 — Exchange Position Reconciliation

The spec §14.5 describes P&L reconciliation but NOT position reconciliation.

Needed: Every N heartbeats, query the exchange for actual open positions. Compare:
- Exchange says: CE 60 lots short @ 67800. Algo says: CE 60 lots @ 67800. ✓
- Exchange says: PE 35 lots short @ 68000. Algo says: PE 36 lots @ 68000. ✗ → ALERT

This catches missed fills, phantom positions, and state drift.

---

### 3.7 — Execution Quality Tracking

No slippage or latency tracking exists.

Needed:
- Track mark price at decision time vs actual fill price for every order
- Track API latency (ms from order submit to fill confirmation)
- Track fill rate (% of orders that fill on first attempt)
- Detect degrading execution quality and alert

---

### 3.8 — Wind-Down Strategy

**Missing entirely.**

The algo has no concept of "purpose served — gracefully exit." It runs until expiry or max_loss.

Institutional approach:
- **Profit target**: If net P&L exceeds X, start reducing positions (don't add on adjustments, just let theta decay remaining positions).
- **Time-based wind-down**: In the last 2 hours, close positions that are >80% profitable rather than waiting for close-at-5.
- **Rolling exit**: Close the most profitable positions first to lock in gains while maintaining the least profitable as hedges.

---

### 3.9 — Multi-Session Risk Aggregation

mmm_019d87 and mmm_09cde2 ran simultaneously with DIFFERENT parameters on the SAME underlying (BTC). Their combined lot exposure was ~100 lots. There is no aggregated risk view.

Needed: Dashboard showing total exposure across all active sessions, combined delta, combined max loss, margin utilization.

---

### 3.10 — Configurable Defaults That Prevent Self-Harm

User-configurable params that were set to dangerous values:
- `whipsaw_limit=30` (should have floor of 3-5)
- `cooldown_on_reversal=False` (should warn or prevent)
- `min_trigger_move=2` (should have floor based on underlying vol)
- `max_lots_per_side=200` (should have circuit breaker)

Proposed: Implement "guardrail validations" on parameter changes — warn when settings are outside the safe range, require explicit override.

---

## PART 4: PRIORITY RANKING

| Priority | Item | Type | Impact |
|----------|------|------|--------|
| **P0** | Frozen position double-counting fix | Bug | Prevents exponential lot growth |
| **P0** | Per-adjustment lot cap | Missing feature | Single-trade risk limit |
| **P0** | Trade data persistence (mmm_trades table) | Missing feature | Audit trail, compliance, backtesting |
| **P1** | Anti-amplification circuit breaker | Missing feature | Runaway prevention |
| **P1** | Fee tracking implementation | Missing feature | Accurate P&L |
| **P1** | Parameter guardrails (min floors) | Missing feature | Prevent unsafe configs |
| **P1** | Exchange position reconciliation | Missing feature | State integrity |
| **P2** | Volatility regime detection | Enhancement | Adaptive behavior |
| **P2** | Wind-down / profit-taking strategy | Enhancement | Institutional exit logic |
| **P2** | mmm_f48816 data integrity fix | Bug | Historical data accuracy |
| **P2** | Execution quality tracking | Enhancement | Slippage awareness |
| **P3** | Greeks-based decisions | Enhancement | Institutional risk management |
| **P3** | Dynamic parameter tuning | Enhancement | Self-optimizing algo |
| **P3** | Multi-session risk aggregation | Enhancement | Portfolio-level view |
| **P3** | Reversal count accuracy fix | Bug | Dashboard clarity |

---

## PART 5: BOTTOM LINE

**The algo is profitable** — both expired sessions ended in the green despite aggressive oscillation. The core logic (trigger → adjustment → reversal detection → close-at-5 → near-expiry shutdown) works end-to-end.

**The biggest risk is amplification**: The positive feedback loop between position size and adjustment size is the single most dangerous characteristic. It worked out in these sessions because BTC options have high theta decay near expiry, so close-at-5 cleaned up positions faster than they grew. In a session where premiums oscillate but DON'T decay (e.g., weekly/monthly options), the amplification loop would be catastrophic.

**Three things will make this institutional grade**:
1. Fix the frozen position double-counting (P0 bug)
2. Add per-adjustment lot cap + circuit breaker (P0 feature)
3. Build a persistent trade journal with every order recorded (P0 compliance)

Everything else is enhancement. These three are foundational.

---

*Report generated: February 17, 2026*
*Data source: SQLite mmm_sessions.db, MONEY_POWER_CALCULATION_LOGIC.md*
*Sessions analyzed: mmm_019d87, mmm_09cde2, mmm_f48816*
