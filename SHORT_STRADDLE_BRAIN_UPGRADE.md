# SHORT STRADDLE BRAIN UPGRADE
**Independent strategic review of the MMM "Short Straddle with Adjustment" strategy**
_Author: Strategic review pass — 2026-04-19_
_Scope: Logic critique only. No code changes, no refactor._

---

## 0. Executive stance

This is a **competently engineered theta-harvesting engine wrapped around a naive trading thesis.** The code has excellent **operational plumbing** (fill sync, generation guards, margin tiers, pin UX, 3-layer stale monitor, split ledger, reverse mode isolation). But the **alpha layer** — the part that decides *when, how much, and where* to trade — is mechanically premium-reactive and volatility-blind. It will make steady money in chop and surrender it back (with interest) on trend days and vol expansions.

The bot cannot distinguish "quiet Tuesday" from "CPI morning." That is the single most important thing to fix.

---

## 1. CURRENT LOGIC DECODED

### 1.1 What the strategy actually does, in plain language

1. **Open**: sell ATM call + ATM put (configurable `initial_lots`, default 10 × 0.001 BTC).
2. **Heartbeat every ~5 min**: re-read chain, compute P&L, update trigger snapshots.
3. **Trigger**: if the premium of *either* leg has risen ≥ 10% above its snapshot → that leg is "the aggressor." Sell more of the *opposite* leg (the "hedge") to generate income that offsets the aggressor's MTM loss.
4. **Lot sizing**: compute the dollar loss on the aggressor → divide by the hedge's premium per BTC → add 5% buffer → ceil. Multiply by a cascade (gamma-aware 1.0–1.3×, breakeven 1.0–3.0×, trend -30%, gamma severity 1.1–1.5×), then cap at 3× of raw.
5. **Shift**: when the hedge leg's premium decays below $50, freeze that strike and re-establish the hedge at a new OTM strike closer to current spot.
6. **Close-at-5**: any position whose bid premium falls to ≤ $5 is bought back early (locking in most of the profit).
7. **Replenish**: if a side is fully closed but the other still has exposure, re-sell on the empty side to restore the straddle/strangle shape.
8. **Capacity engines**:
   - **M1 Harvester** closes frozen positions that are ≥40% in profit when capacity pressure ≥0.5.
   - **M2 Recycler** — on hitting position cap, buys back cheap frozen lots and re-sells closer-to-ATM at ≥2.5× the avg closed premium.
   - **M3 Asymmetry Boost** — loosens M1 when one side is ≥5× heavier than the other.
9. **Safety**: max_loss $100 → pause+close; max_adjustments 500 → pause; 15 min pre-expiry stop-adjusting; 5 min pre-expiry auto-close.
10. **Optional overlays** (default OFF): regime filter (vol / gamma / trend), margin guardian, perpetual-hedge, reverse mode.

### 1.2 Implicit assumptions

| # | Assumption baked in | Where it lives |
|---|---|---|
| A1 | Premium moves are the best real-time proxy for directional risk | 10% trigger, premium-buffer sizing |
| A2 | The market will eventually mean-revert within the session / expiry | entire adjust-and-hold loop |
| A3 | An unhedged directional loss can be recouped by selling *more* of the opposite side | `calculate_lots_to_sell(loss, hedge_premium)` |
| A4 | Exchange liquidity is deep enough that limit orders at mid-price fill in <4 minutes | executor reprice loop |
| A5 | 5-minute granularity is fast enough to manage gamma | `adjustment_interval=300s` |
| A6 | Regime detection is optional polish, not a primary filter | defaults: `regime_enabled=False`, `margin_monitor_enabled=False`, `perp_hedge_enabled=False` |
| A7 | A flat $100 max-loss represents acceptable risk for a 10-lot BTC straddle | `max_loss_amount=100` |
| A8 | Premium-based triggers auto-adapt to volatility | no IV normalization anywhere in sizing |

**A1, A3, A6, A8 are the dangerous ones.** The rest are engineering trade-offs; these four are philosophy errors.

### 1.3 Where the edge probably comes from

- **Theta on weekly/0DTE BTC options.** BTC options are structurally richly priced vs. realized vol on quiet days. Any disciplined short-vol book captures that spread.
- **Rapid strike shifts + freezing**: keeps the active book close to ATM where theta is fattest.
- **M1 harvester**: opportunistic closing of deep-ITM-decayed frozen lots — this is a genuinely clever piece. It's the only component that *proactively* books profit instead of waiting for close-at-5.
- **Close-at-5**: crystallizing 90%+ of max profit instead of squeezing the last dollar avoids a huge number of gamma-snapback losses. This is probably the single best rule in the book.
- **Execution hygiene**: mid-price limits with amend-in-place repricing avoid the aggressive slippage that kills most retail straddle bots.

What is **not** a source of edge, despite appearances:
- The adjustment mechanism itself. Selling-more-against-an-aggressor is a **Martingale in options clothing** — on mean-reverting days it works; on trend days it is ruinous. The gamma-aware multiplier makes this worse, not better, by adding size into a move.
- The regime filter — it's off by default.

---

## 2. HIDDEN WEAKNESSES

### 2.1 Trend-day risk (severity: CRITICAL)

BTC routinely prints 3–5% intraday moves. The trend tiers fire at **0.5 / 1.0 / 1.5 / 2.0%** — which sounds tight until you realize:

- With `regime_enabled=False` (default), these tiers **do nothing.** The operator must opt in.
- Even when on, tier T3 (full sell-block) fires at **1.5%**. On a 3% trend day, the algo sells lots into the move from spot to T3, then stops — but by then it's already loaded.
- The `calculate_lots_to_sell` formula does **not know about trend**. It only knows the loss is big, so it sells more. The trend-tier-1 lot reduction (30%) is applied *after* the formula — but formula output is already scaled by breakeven (up to 3×) and gamma-aware (up to 1.3×).
- Gamma-aware multiplier **adds size as excess_pct rises** (1.3× at ≥200% excess). On a trend day, excess_pct keeps rising, so each adjustment sells more than the last. That's the Martingale.
- There is no **second-derivative check** (is the move accelerating?). The `trend_acceleration_pct=0.5%/600s` is the only thing close, and it merely bumps the tier.

### 2.2 Gamma explosion near expiry (severity: HIGH)

- `gamma_near_expiry_multiplier=0.5` tightens the gamma cap in the last 30 min. That's the *only* time-aware scaling.
- Between 30 min before expiry and `auto_close_mins=5`, the algo is still adjusting. For 0DTE on BTC, 30 min is an eternity. Five minutes is where most of the pin-risk lives.
- **Pin risk is not modeled at all.** No detection of "spot oscillating ±$20 around a 25k strike with 15 min left." That pattern generates infinite whipsaw under a 10% trigger.
- `whipsaw_window_mins=30` with `whipsaw_spot_move_pct=0.3` gives a counter, but the counter only *caution-flags* at score 2 and *cooldowns* at score 4 — too lenient for 0DTE.

### 2.3 Volatility expansion risk (severity: CRITICAL)

- **The lot sizing formula does not reference IV or realized vol anywhere.** A 10% premium rise from $30 → $33 (quiet day) triggers the same response as $30 → $33 caused by an IV spike from 45 → 55 (regime break). The first is noise, the second is the start of a loss cycle.
- Vol regime *can* block sells (`vol_regime_action='block_sells'`), but it does **not** reshape sizing when sells are allowed.
- IV spike threshold `vol_iv_spike_pct=30` over 5 beats is way too lenient for crypto. 30% IV rise in 25 min (5 × 5-min beats) is a black swan, not an early warning.
- There is no **IV-rank / IV-percentile** context. The bot has no idea if today's IV is the 10th or 90th percentile vs. last 30 days.

### 2.4 Over-adjustment risk (severity: HIGH)

- `max_adjustments=500` per session. At 5 lots per adjust, that's 2,500 lots — 25× the per-side cap. The session hits position caps and M2 kicks in, which *recycles* lots to closer strikes — which then triggers more.
- On a bad day, the algo can do 50+ adjustments in the last hour. Each one has execution cost and each one can fire during a directional move.
- The `lot_velocity_limit=30 lots/30 min` is the main brake. That's one brake. There's no brake on *number* of adjustments per hour, only on *lots* per hour.

### 2.5 Whipsaw churn (severity: MEDIUM)

- The reversal detector exists (`mmm_reversal.py`) but its cooldown default is `reversal_cooldown_seconds=0` — essentially disabled.
- The whipsaw guard is a scored system (caution/restrict/cooldown) with thresholds 2/3/4 — modest and only triggered by *spot* moves, not by *sequential aggressor flips*.
- When the trigger snapshot updates after every adjustment, a choppy market continually resets the baseline, so every mini-move becomes a new trigger.

### 2.6 Margin traps (severity: HIGH)

- `margin_monitor_enabled=False` is the default. That's the biggest safety feature in the system and it ships **off.**
- Without it, a stressful day will rack up positions until the exchange auto-liquidates — which is catastrophically worse than the bot stopping at 85% utilization.
- Max total exposure `max_total_exposure=0` (auto → 2 × `max_lots_per_side`). On Delta, 200 short BTC-option lots near ATM near expiry is a *lot* of gamma.

### 2.7 Slippage / execution drag (severity: MEDIUM)

- Mid-price post-only limits with amend-in-place is **good**. But 4 minutes of reprice looping during fast moves is an eternity — the market has already moved further by the time the fill comes through.
- No **slippage attribution**: the algo doesn't log realized fill price vs. intended mid-price, so it can't adapt execution behavior based on recent fill quality.
- No concept of "walk the book" or "chase more aggressively when losing control" — repricing always targets mid.

### 2.8 Tail / black swan scenarios (severity: CRITICAL)

- A sudden 5% gap (common in crypto on exchange outages, liquidation cascades, US session opens): the 5-min heartbeat means the algo can wake up already massively offside, with zero intermediate adjustments done.
- No correlation break detection (e.g., BTC vs. equities divergence that precedes vol moves).
- No event-calendar awareness (FOMC, CPI, NFP). The algo will happily sell ATM straddles going into an 8:30 AM ET CPI print.
- No circuit breaker on **total-P&L velocity**. Max-loss is a level, not a rate.

### 2.9 Silent failure modes that are structural, not operational

- **Frozen positions' gamma is invisible to the trigger system.** Only active-strike premium drives the trigger. A session with 80 frozen lots across 5 old strikes + 20 active lots at the new strike can have *massive* short gamma and the trigger only sees the 20 active. The `min_frozen_trigger_dollar=0.2` fallback helps, but is an afterthought.
- **Replenish OCS mode bypasses nearly every gate** (regime, cooldown, near-expiry, velocity). The rationale (restore hedge) is sound, but in practice OCS fires during exactly the worst moments — when the hedge side just got blown out.
- **Close-at-5 is a flat threshold, not relative**: a position entered at $50 closing at $5 is 90% profit; a position entered at $8 closing at $5 is 37.5% — these should not be treated the same. Worse, an original-entry leg entered at $200 closing at $5 is amazing (97.5%) — but it takes much longer and could turn against you many times before getting there.

---

## 3. BRAIN UPGRADES (logic only, no code)

Proposed improvements, grouped. Each has a one-line "why" and a one-line "shape."

### 3.1 Regime-first architecture

- **Make the regime filter ON by default**, with sensible crypto-specific thresholds. Why: default-off safety is theater. Shape: `regime_enabled=True`, `margin_monitor_enabled=True`, `perp_hedge_enabled=True (atm_only)`.
- **Add IV-percentile awareness.** Why: 30% IV spike is black-swan-tier; the bot needs graded response. Shape: maintain 30-day IV percentile; scale `initial_lots` down when IV is in top quartile, up in bottom quartile. At IV-rank >80, go to strangle (wider strikes) instead of straddle.
- **Vol-of-vol kill switch.** Why: IV spikes precede premium spikes; the bot should stop selling *before* premiums blow out. Shape: if 5-min IV realized change > 2σ over last 90 min → block new sells for 30 min.

### 3.2 Smarter triggers

- **Normalize triggers by ATM IV.** Why: 10% of a $20 premium ≠ 10% of a $200 premium in risk terms. Shape: trigger threshold = max(`min_trigger_move_pct`, K × IV^0.5). When IV doubles, trigger threshold widens.
- **Add a spot-distance trigger** alongside the premium trigger. Why: premium can lag on illiquid strikes; spot distance is the real risk driver. Shape: if spot has moved > X% from entry regardless of premium move → trigger.
- **Suppress triggers immediately after strike shift.** Why: new strike has a fresh snapshot; first 1–2 beats after shift create false triggers. Shape: cooldown = max(2 beats, 10 min) post-shift.
- **Add a gamma-based trigger override.** Why: net-short gamma on the portfolio is the real risk. Shape: compute portfolio short-gamma; if gamma jumps >X% beat-over-beat, force an adjustment evaluation even without premium move.

### 3.3 Volatility-aware behavior

- **Scale `initial_lots` by IV-rank, not config.** Why: same notional risk across regimes. Shape: base_lots × (1 / sqrt(IV_rank_factor)).
- **Scale the 3× combined lot multiplier by IV-rank.** Why: aggressive multipliers in high vol = blowup. Shape: at IV-rank > 70, cap combined multiplier at 1.5× instead of 3×.
- **Switch to strangle mode at high IV-rank.** Why: ATM gamma is dangerous when IV is already elevated. Shape: at IV-rank > 75, auto-shift strikes to ~0.25Δ instead of ATM.

### 3.4 Time-of-day & event rules

- **Event calendar integration.** Why: FOMC/CPI/NFP reliably pre-expand IV; selling straddles into them is free money *for the counterparty*. Shape: maintain a simple JSON calendar; block new initial entries within ±60 min of listed events; block *all* sells within ±15 min.
- **Session-of-day risk scalars.** Why: US open (13:30 UTC) is reliably more volatile than Asian afternoon; treat them differently. Shape: session-risk-multiplier table applied to lot sizing.
- **Time-from-open no-trade zone.** Why: the first 10 minutes of BTC US session is noise with outlier moves. Shape: no initial entries, no adjustments during a configurable "hot window."

### 3.5 Trend / regime filters (tightened)

- **Earlier trend tiers + harder action.** Why: T3 at 1.5% is too late for a trend day. Shape: T1 at 0.3%, T2 at 0.7%, T3 at 1.2%, T4 at 1.7%. At T2 in current vol regime, **also reduce existing exposure** (not just block new sells).
- **Trend-detected hedge instead of trend-detected block.** Why: blocking sells leaves the existing book still short; delta hedging with perp neutralizes. Shape: at T2+, auto-fire perp hedge to bring portfolio delta to ±0.05 BTC.
- **Use ATR-normalized tiers.** Why: 1% move is different in a 1% ATR vs. a 4% ATR regime. Shape: tier thresholds = multiples of 30-day ATR, not absolute %.

### 3.6 Profit lock system

- **Ladder the close threshold, don't flatten it.** Why: a $5 bid on a position entered at $50 is 90% profit; on a position entered at $10 it's 50% — they deserve different treatment. Shape: close-at = max($5, 10% of entry_premium). Positions that decay fast (ATM at high IV) get harvested sooner.
- **Trailing profit stop on the portfolio.** Why: current system has `max_loss_amount` but no equivalent for "we're up $400, don't give it all back." Shape: once session P&L > $X, any drawdown of Y% from peak closes all.
- **M1 harvester profit threshold scaled by time-to-expiry.** Why: 40% profit near expiry is less valuable than 40% with a day left. Shape: threshold = 40% × (1 + expiry_proximity_factor).

### 3.7 Dynamic hard stop

- **Trailing max-loss, not fixed.** Why: $100 max on a session that peaked at +$500 should stop at +$200, not -$100. Shape: max_loss = max(-$100, peak_pnl - $200).
- **Loss-velocity circuit breaker.** Why: losing $50 in 5 min is structurally different from losing $50 in 3 hours. Shape: if loss rate > $X/min for 3 consecutive beats → pause + close.

### 3.8 Re-entry logic

- **Kill-then-wait before re-entry.** Why: after a max-loss stop, the current system requires manual resume; fine — but there's no "clean-slate checklist" (has vol normalized? has trend tier reset? is it still a hot window?). Shape: re-entry guard checks IV not in top quartile, no trend tier > T1, not in event window.
- **Replenish should respect regime.** Why: OCS bypass is too broad — replenishing into a vol spike is bad. Shape: OCS bypass *only* for margin-relief replenish; normal replenish still respects vol regime.

### 3.9 No-trade zones

- Pre-defined: event windows, pin zones (last 10 min with spot within $50 of a strike with >X oi), after-unusual-volume windows, during known exchange maintenance windows.

### 3.10 Adaptive sizing

- **Kelly-style scaling** on recent win rate: if last 10 sessions had 8 wins avg $X → size up slightly; 3 wins → size down. Why: adapts to whatever the live edge actually is. Shape: size multiplier in [0.5, 1.5] tied to trailing Sharpe.
- **Size by gamma budget, not lot count.** Why: lot count is a poor risk proxy across strikes and IV regimes. Shape: target max portfolio short-gamma as primary constraint; lot counts derive from that.

### 3.11 Hedge overlays

- **Default-on perp delta hedge** with a small band. Why: eliminates the dominant P&L driver on trend days with minimal theta cost. Shape: `perp_hedge_enabled=True`, threshold=0.03 BTC net delta, target band ±0.02.
- **Tail hedge (cheap wings).** Why: buying a 2σ OTM strangle as insurance costs ~5–10% of collected theta but caps the tail. Shape: at entry, buy 1 lot each of ~0.10Δ OTM call and put. Revisit daily.
- **Convert to iron condor when threatened.** Why: once the straddle is in T2, the payoff is already asymmetric; buying 1 OTM leg on the threatened side caps loss. Shape: at trend T2, auto-buy cheap OTM protection on aggressor side.

### 3.12 Kill-switch intelligence

- **Multi-signal kill switch**, not just max-loss. Shape: kill if any two of {drawdown > X, IV-rank jump > Y in Z min, trend tier ≥ T3, margin > orange, WebSocket stale > N sec, fill fail rate > M% in last 10 orders}.
- **Outer-loop watchdog**: a separate process that can force-close from a different API key if the main bot becomes unresponsive. (Operational upgrade; worth the complexity.)

---

## 4. DECISION FRAMEWORK (real-money, end-to-end)

If I were running this with real capital, the decision tree would be:

### 4.1 Pre-trade gate (runs before *any* entry)

1. **Calendar check** — is there a known macro event within ±60 min? → NO-TRADE.
2. **Hot-window check** — US open (13:30–13:40 UTC) or Asian close (08:55–09:05 UTC)? → NO-TRADE.
3. **Liquidity check** — is the chain's aggregate bid depth at ±5 strikes below a floor? → NO-TRADE.
4. **Vol regime check** — IV-rank > 85? → REDUCED SIZE + strangle not straddle. IV-rank > 95? → NO-TRADE.
5. **Recent P&L check** — last session loss > 2× avg? → WAIT one session (cool-down).
6. **Technical check** — is price within 0.5 × ATR of a major level (prev day high/low)? → REDUCED SIZE.

If all gates pass → compute sizing.

### 4.2 Entry

7. **Sizing** = base_lots × IV_rank_scalar × recent_performance_scalar × session_risk_scalar. Floor=0.3×, ceiling=1.5×.
8. **Strike selection**: ATM if IV-rank ≤ 60; 0.30Δ strangle if 60–85; skip if >85.
9. **Tail hedge**: buy 1 lot each at 0.08–0.12Δ OTM (both sides).
10. **Enter with post-only mid-price, amend aggressively (reprice every 30s, 3 attempts), then cancel and skip the session if still unfilled** — missed entry is cheaper than forcing entry.

### 4.3 Management loop (every beat)

Each heartbeat, in this order:

11. **System health**: WebSocket age, fill sync lag, stale monitor check. Any fail → HALT immediately.
12. **Margin tier**: at yellow, block new sells; at orange, wind-down; at red+, emergency close.
13. **P&L stops**: max-loss, trailing-drawdown, loss-velocity. Any hit → close all.
14. **Regime**: vol regime, trend tier, event window. Tier ≥ T2 or event within 15 min → block sells + hedge delta with perp.
15. **Greeks check**: portfolio short-gamma within budget? Net delta within band? If delta outside band → perp hedge.
16. **Trigger evaluation**: vol-normalized + spot-distance + frozen-gamma check.
17. **Pre-sell gate check**: after trigger fires, re-check margin/regime/whipsaw. Any new red flag → skip the adjustment.
18. **Size**: compute target lots from *loss OR gamma* whichever is smaller; apply caps (velocity, combined multiplier, IV-scaled ceiling).
19. **Execute**: limit at mid, short reprice loop. Failed fills escalate to "skip this beat, try next" — never chase aggressively.

### 4.4 Exit

20. **Close-at-threshold per-position**: max($5, 10% of entry, 5% of max-ever-premium).
21. **M1 harvest**: time-scaled profit harvesting.
22. **Time stop**: `stop_adjustment_mins` pre-expiry (no new sells); `auto_close_mins` pre-expiry (all closed).
23. **Profit target stop**: once session +X% of initial credit, raise close thresholds (lock in).
24. **Trailing peak stop**: session peak P&L recorded; close all if drawdown from peak > Y%.
25. **Re-entry block**: after exit, wait for regime to normalize + at least one full adjustment interval.

---

## 5. PRIORITY RANKING — TOP 10 IMPROVEMENTS

Weighting: **Impact** (4), **Safety** (4), **Simplicity** (2), **Real-money usefulness** (3). Total max = 13.

| Rank | Upgrade | Impact | Safety | Simplicity | Real-$$ | Total | Rationale |
|---|---|---|---|---|---|---|---|
| 1 | **Enable regime filter + margin guardian by default** with crypto-tuned thresholds | 4 | 4 | 2 | 3 | **13** | Biggest safety gap. The code exists; it's just off. |
| 2 | **Default-on perp delta hedge** (`atm_only` + trend-tier forced hedging) | 4 | 4 | 1 | 3 | **12** | Eliminates trend-day ruin. Code exists. |
| 3 | **IV-percentile aware sizing** + strangle-mode switch at IV-rank > 75 | 4 | 3 | 1 | 3 | **11** | Fixes vol-blindness. Requires building IV-rank tracker. |
| 4 | **Trailing drawdown stop** (lock peak P&L) | 3 | 4 | 2 | 3 | **12** | Keeps winning sessions from becoming losers. Trivial logic. |
| 5 | **Tighten trend tiers + force hedge at T2** | 4 | 4 | 2 | 2 | **12** | Current tiers fire too late for crypto. |
| 6 | **Event calendar no-trade zones** (FOMC/CPI/NFP) | 3 | 4 | 2 | 3 | **12** | Highest $/line-of-code ratio. Static JSON list. |
| 7 | **Ladder close-at threshold** (max($5, 10% of entry)) | 3 | 2 | 2 | 3 | **10** | Faster theta crystallization on small-premium positions. |
| 8 | **Loss-velocity circuit breaker** ($/min over N beats → halt) | 3 | 4 | 2 | 2 | **11** | Catches tail events before max-loss level is hit. |
| 9 | **Gamma budget as primary size constraint** (lots derive from gamma target) | 4 | 3 | 1 | 2 | **10** | Architecturally correct; larger lift. |
| 10 | **Whipsaw counter tightening + aggressor-flip penalty** | 2 | 3 | 2 | 2 | **9** | Cheap way to suppress churn sessions. |

**Tier-2 honorable mentions** (rank 11–15): cheap OTM wing overlay, post-stale-WS HALT, session-of-day risk scalars, pin-zone detection, slippage attribution telemetry.

---

## 6. FINAL VERDICT

### 6.1 Score: **6.0 / 10**

Breakdown:
- **Engineering**: 8.5/10 — fill sync, generation guards, margin tiers, split ledger, reverse mode isolation, replenish OCS, trigger pin UX, hot-reload param system, sealed test discipline. This is institutional-grade *plumbing*.
- **Risk management**: 5/10 — safety layers exist but default OFF. Max-loss is a level, not a system.
- **Alpha layer (strategy)**: 4.5/10 — pure premium reactivity, volatility-blind sizing, Martingale-flavored adjustments, no event awareness.
- **Execution**: 7/10 — mid-price limits with amend-in-place is above retail average; missing slippage attribution and post-failure escalation logic.
- **Observability**: 7/10 — activity log, guardian, fill sync is good; missing per-decision reasoning traces and realized-vs-expected P&L attribution.

The 6.0 reflects: **will make money on average days, will give it all back on outlier days.** That is the classic short-vol profile — but *this* bot does not have the vol awareness, event awareness, or dynamic sizing that separates professional short-vol from retail short-vol.

### 6.2 What "institutional-grade" looks like from here

To get to 8.5+:

1. **Treat volatility as a first-class input, not a side effect of premium.** IV-rank, IV-percentile, IV-of-IV, term-structure skew. Everything in the sizing and trigger path keys off at least one of these, not just a % of premium.
2. **Default-on safety, opt-OUT not opt-IN.** Regime, margin guardian, perp hedge, loss-velocity breaker, trailing drawdown — all default on. The bot should require an operator to *weaken* it, not to *strengthen* it.
3. **Event-calendar and session-of-day gating.** Hard-coded no-trade windows. These are nearly free and reliably profitable to implement.
4. **Gamma budget as the primary sizing axis.** Lots are a derived quantity, not an input. Every sell is compared against a portfolio-level short-gamma target, and sells that would blow the budget don't fire.
5. **Tail hedge always on.** A permanent 0.10Δ strangle long costs ~10% of weekly theta and caps disaster. Institutional books *always* run some form of tail hedge for exactly this reason.
6. **Trailing drawdown with profit ratchet.** Once session equity is up X%, never let it fall below X - Y%. Single most under-used rule in retail short-vol.
7. **Execution telemetry with feedback**. Log intended-fill-price vs. actual, track per-symbol and per-side fill quality, adapt the reprice cadence if quality degrades — don't just reprice blindly 4 times.
8. **Per-session forensic record** of every decision (why did we adjust, why did we size X, why did we shift). Sort monthly by outcome, look at loss-session decision patterns. The bot's learning loop is currently human-in-the-loop; it should be continuous.
9. **A paper-trading replay harness** that re-runs the last 30 days of tape with candidate parameter changes. Most "brain upgrades" should be proven in replay before ever touching live capital.
10. **Explicit operator brief for each session start**: current IV-rank, upcoming events today, last 5 sessions outcome, any parameter overrides active. A human glance-check before arming.

### 6.3 One-line summary

> **The bot's engineering is a solid Volvo. The strategy driving it is a nervous teenager. Give the Volvo a seasoned driver — then it's a professional vehicle.**

---

## Appendix A — Things the code does right (credit where due)

- Three-layer stale-monitor guard (post-P0 incident fix) is textbook defense-in-depth.
- Fill sync with strict order-id matching (no size heuristics) is the right choice.
- Split ledger + `_being_closed` invariants: hard-won and well-hardened.
- M1 Harvester: the single smartest alpha mechanism in the bot.
- Close-at-5: conceptually correct, even if the flat threshold is crude.
- Trigger pin system: good human-override UX.
- Reverse mode isolation (hard if/else, never mix with ce/pe): architecturally disciplined.
- Hot-reload param system: lets you tune in flight without restart — rare in bots of this complexity.
- CLAUDE.md and MMM_LAST_3_SESSIONS.md institutional memory discipline: this is probably the most under-appreciated safety layer in the whole system.

---

_End of report._
