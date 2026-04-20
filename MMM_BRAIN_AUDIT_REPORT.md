# MMM Algo Brain Upgrade Report

**Audit type:** Independent institutional trading-logic audit (read-only, no code changes)
**Repository:** `WorkingBot`
**Audit target:** MMM (Money Mind & Method) BTC 0DTE short-straddle adjustment engine — full trading brain
**Date:** 2026-04-20

---

## Executive Verdict

**6.5 / 10** — A well-engineered short-straddle adjustment engine that has been hardened by real incidents (stale monitor, hedge-break, position-cap leak) and now has multi-layer safety scaffolding. **But it remains a reactive premium-decay machine, not a thinking trader.** It has no opinion about the market it is selling into. The brain is *defensive* (lots of guardrails, lot caps, gamma zones, regime tiers), but *not strategic* — there is no model of *when not to play*, no model of edge, no model of cumulative day/week risk, no liquidity or microstructure sense, and no learning loop. Production-safe at small size with a supervising operator. Not yet institutional.

---

## What Is Strong

1. **Single canonical P&L formula** (`mmm_pnl_core.compute_current_total_pnl`) consumed by every safety check including reverse-mode P&L — eliminates a huge class of "max-loss didn't fire because two code paths disagreed" bugs.
2. **Layered safety**: hard stop thread + Guardian G1–G5 + Margin Guardian tiers + ATM Shield + regime escalator + position cap + close_at_5 + Whipsaw block. Defense-in-depth is real.
3. **Hard mutual-exclusion architecture for Reverse Mode** (the explicit `if/else` invariant) — orthogonal subsystems don't cross-contaminate state. This is unusual discipline.
4. **Unified position ledger** with FIFO `_remaining_bc` accounting, status tags, and recompute views — the migration from sparse dicts was the correct call and removed a class of double-counting bugs.
5. **Adjustment lot sizing is multi-factor, not naive** — gamma, breakeven proximity, trend boost/penalty, OTM scaling, data-confidence gate, and a hard combined-multiplier ceiling. Most retail bots multiply premium and pray.
6. **Documented incident memory** (`mmm_workdone_march.md`, `MMM_LAST_3_SESSIONS.md`, three-layer stale-monitor fix, F1–F5 hedge-break fix) — institutional memory lives in the repo, not just heads.
7. **Frozen-vs-active separation** with strict cap on `total_lots = active + frozen` (2026-04-19 fix) closes the silent 2× exposure leak.
8. **VIPSO/Smart Whipsaw** has a real composite detector with token budget and pressure override — architecturally serious even if currently mis-wired (see weakness W2).

---

## Hidden Weaknesses

### W1 — The brain has no entry edge model
There is no IV regime check, IV-percentile filter, term-structure check, expected-move vs. premium-collected check, or "should we even open a straddle today?" gate before entry. The bot sells whatever the operator points it at. **Edge is assumed, not measured.** If realized vol > collected premium for a stretch, the adjustment machinery only delays the bleed.

### W2 — Smart Whipsaw control plane is dishonest
Per the VIPSO audit you just ran: `whipsaw_smart_enabled` is non-binding in `select_engine()`, and five Smart parameters are exposed/validated/hot-reloaded but **not consumed by `multi_gate_decide()`**. Operator believes they're tuning and they aren't. In a real-money system this is a P0 governance bug, not a UI bug.

### W3 — Loss recovery has no convergence criterion
`calculate_lots_to_sell` is reactive: more loss → more lots, capped by multipliers and the position cap. But there is no rule of the form *"if we have hedged N times in the same direction in M minutes, stop and reassess."* Position cap is the only floor — and once you hit it the side is dead until frozen lots drain. That's a correct cap, but it's a brick wall instead of a brake.

### W4 — Frozen positions are passively held
M1 Harvest only fires when `capacity_pressure ≥ 0.6`. A session running at 30% capacity can accumulate frozen losses for hours before harvest looks at them. If volatility moves *back toward* a frozen strike, gamma reasserts and the harvester is asleep.

### W5 — Hard stop is async to heartbeat
The `_hard_stop_guard_thread` polls every ~5–10s while the heartbeat may place new adjustments in the gap. The threading event prevents double-fire but not a fresh sell at T=4.5s before the guard fires at T=5s. In a fast move, that's one extra hedge at the worst price.

### W6 — Margin Guardian is a lot-count proxy
`mmm_safety` estimates margin from lot counts, not the exchange's actual maintenance margin. Anything else on the account (perp positions, other strategies, withdrawals, mark-to-market collateral haircuts) is invisible. On Delta this can diverge meaningfully during stress.

### W7 — No liquidity, spread, or microstructure check before sell
`find_new_strike` ranks by proximity to `shift_target_premium`. It does not look at bid-ask spread, top-of-book depth, recent trade volume, or stale-quote age. In the last 30 minutes of 0DTE this is exactly when chains thin and the bot is *most* likely to shift.

### W8 — Trigger snapshot initialization race
First trigger is set to fill premium. A 3–10 second gap between fill and first heartbeat in a fast tape can seat the trigger above where the loss already started. The first adjustment then never fires until much deeper, by which time the lot-sizing calculation produces a bigger sell at a worse strike.

### W9 — Constants imply a specific underlying and regime
`shift_threshold ~ $25–70`, `close_at_threshold = $5`, `theta_acceleration_window = ~120m`, `gamma_hard_limit = $5000`, `trend_tier1 = 0.5%`, `max_loss = $100` — these are tuned for *current BTC, current vol, current account size*. The system has no `regime_calibration` layer that re-derives them when conditions change.

### W10 — Replenish bypasses too many gates
By design, replenish overrides wind-down, regime BLOCK_ALL_SELLS, cooldown, near-expiry, and velocity limits to restore a hedge. That's defensible — but it means a stress regime that *correctly* told you to stop selling will still sell on the unhedged side. There is no upper bound on what replenish can spend.

### W11 — No consecutive-loss / multi-day circuit breaker
The bot has no awareness of "three losing 0DTEs in a row" or "this week's drawdown is X% of capital." Each session starts fresh. The operator is the circuit breaker.

### W12 — Reverse Mode is an unhedged directional short
It is gated, alternation-enforced, and P&L-tracked — but it is still a short option with no hedge, activated when the *core* book is healthy. That correlates worst-case losses across modes: the regimes where reverse looks most attractive (clear trend) are the same regimes where the core straddle is bleeding.

### W13 — `incomplete=True` loss calc still proceeds
A frozen-position premium fetch failure marks the loss calculation incomplete and fires a warning, but the adjustment runs on the partial number. In an API outage, you systematically under-hedge.

### W14 — No fee, slippage, or close-cost reservation in max-loss
Max loss check fires on estimated P&L; no buffer is held back for the cost of *executing* the close. On an at-the-edge breach you can blow through the cap during liquidation.

---

## Missing Intelligence Layers

1. **Regime classifier (entry gate)** — IV rank/percentile, RV/IV ratio, term-structure slope, recent realized-vs-implied. A simple "do not initiate if RV/IV > 1.1 over last 24h" would have prevented many bad starts.
2. **Expected-move vs. collected-premium ledger** — at entry, log straddle width vs. 1-σ implied move. If after N sessions premium collected < realized move, the strategy has no edge in the current regime; flag.
3. **Microstructure layer** — bid-ask spread cap, top-of-book depth requirement, stale-quote detector, last-trade-age check before any sell or shift.
4. **Loss-velocity / divergence brake** — "if loss is widening faster than we can hedge for K beats, stop adding lots and switch to defensive close." Distinct from position cap.
5. **Cumulative risk memory** — daily loss budget, weekly drawdown cap, consecutive-loss kill switch with cool-off.
6. **Liquidity-aware strike selection** — rank shift candidates by `(premium_distance_score × liquidity_score)`, not premium alone.
7. **Real margin API integration** — query Delta for actual maintenance margin and free collateral, not lot proxy.
8. **News/event calendar gate** — block entries and force flat over scheduled high-impact events (CPI, FOMC, BTC ETF flows). Even a static cron would beat what's there.
9. **Adverse-selection meter on shifts** — track post-shift realized loss vs. pre-shift expected. If the bot is being run over on its own shifts, dampen.
10. **Whipsaw control-plane truthing** — fix the dead knobs and the `whipsaw_engine` vs. `whipsaw_smart_enabled` semantic split (already in your VIPSO P0 list).
11. **Self-replay learning loop** — re-run last N sessions weekly under counterfactual params; report which dead knobs actually would have helped.
12. **Per-side IV curvature monitor** — call/put IV skew shift is the single best leading indicator that one side is about to move; the bot ignores it.

---

## Dangerous Future Failure Scenarios

1. **Sustained one-way trend day at small position** — the harvester sleeps, frozen lots accumulate quietly, replenish bypasses regime block, position cap eventually slams shut on the trending side, max loss fires near expiry on a wide chain. Plausible loss: 3–5× normal cap because shifts during low liquidity slip badly.
2. **Flash IV spike on a news candle** — premiums double in seconds, trigger fires on both sides, BOTH path pauses awaiting operator decision (not a hedge), and during the pause the underlying continues. Bot waits, exposure grows.
3. **API/WS partial outage** — premium fetches fail intermittently; `incomplete=True` losses underestimate true PnL; bot under-hedges; max-loss fires late.
4. **Recycling premium-decay race** — Phase A buyback completes, chain decays during the few seconds, Phase B can't find the required premium ratio, restored buyback leaves you net flat lots but down by execution costs; repeat.
5. **Stale chain candidate at end-of-day** — Pre-scanned shift candidate at beat T is taken at T+5s with 30% premium decay, shift executes far below `shift_target_premium`, immediate re-shift required.
6. **Reverse mode + core straddle aligned losses** — strong directional move triggers reverse on top of an already-bleeding core; both lose simultaneously; reverse's $100 cap is checked late.
7. **Consecutive 0DTE losing streak** — five $100 losses in a week. No system flag. Operator psychology determines whether bot runs Monday.
8. **Margin overstatement** — perp positions opened separately, lot-proxy margin guardian shows GREEN while real margin is at YELLOW; margin call during a stress beat.
9. **0DTE last-15-min illiquidity** — `auto_close_mins=5` works but between minute 15 and minute 5 you can still adjust into a chain that has no real bid. Slippage is the silent loss.
10. **VIPSO truth gap during incident** — operator disables Smart in UI to revert to Legacy under stress, behavior doesn't change, escalation continues.

---

## Highest ROI Improvements (ranked)

1. **Fix the VIPSO truth gap** — single source of truth for `whipsaw_engine`, kill or wire the dead knobs, fix replay state reset. (P0; already in your audit.)
2. **Daily loss budget + consecutive-loss circuit breaker** at the operator/account level above sessions. Cheap; massive tail-risk reduction.
3. **Microstructure gate before any sell or shift** — minimum top-of-book depth + max bid-ask spread % + max quote age. Reject the order, log, alert. Probably the single highest ROI defensive improvement.
4. **Loss-velocity brake** — independent of position cap, stop adding lots if loss widens faster than hedge income for K beats; downgrade to defensive close.
5. **Real margin API integration** — replace lot-proxy in margin guardian with exchange-backed reading.
6. **Entry regime gate** — RV/IV ratio + IV percentile + term slope. A 5-line check would skip the worst entry days.
7. **Slippage / close-cost reservation in max-loss** — hold back ~10% of cap for liquidation cost.
8. **Harvest-on-volatility-snapback** — fire harvest scan independent of capacity pressure when a frozen strike's gamma rises above a threshold.

---

## Quick Wins

- **Hardcode dead Whipsaw params or wire them.** Two-hour change. Removes a real risk vector.
- **Reduce hard-stop async gap** — make the heartbeat re-check `_hard_stop_triggered` immediately before each `engine.execute_adjustment` call.
- **Trigger snapshot guard** — after first fill, wait one beat or use VWAP of first 3 quotes before locking trigger.
- **`incomplete=True` should pause adjustments**, not proceed with partial loss. Toggle behavior.
- **Add bid-ask spread % cap** to `_rank_strikes` (reject if spread > X% of mid). One filter, large benefit.
- **Daily loss tracker file** — append session result, refuse new session if rolling-3-day loss > Y. ~30 lines.
- **Replenish: cap total replenish lots per session** at some multiple of `initial_lots`. Prevents unbounded defensive spend.
- **Log slippage per fill** (expected vs. actual) into a CSV; you can't improve what you don't measure.
- **Min OTM distance on shift after gamma-DANGER bypass** — currently bypassed cleanly for STRADDLE_WITH_ADJUSTMENT, but log the bypass with severity so it's visible.

---

## Advanced Upgrades

1. **Realized-vs-implied edge tracker per regime** — a rolling ledger of (premium_collected, realized_move, fees, slippage) bucketed by IV regime. Gate entry on positive expected value.
2. **Online parameter adapter** — reinforcement-learning-lite: per-week, per-regime, suggest param deltas (shift threshold, harvest %, lot scalars) backed by replay PnL. Suggest only; human approves.
3. **Greeks-aware hedge sizing** — adjustment size driven not by USD loss but by net delta + gamma + vega exposure to neutralize, with notional cap.
4. **Dynamic perp delta hedge** — currently disabled by default. With a real delta model, perp hedging is the cheapest convexity reducer available.
5. **Cross-strategy portfolio risk overlay** — single account-level risk module that sees MMM + grid bot + reverse + manual positions and enforces aggregate VAR/margin/loss limits.
6. **Liquidity-aware execution** — split large sells into TWAP slices over N seconds when book depth is thin; abort if mid moves > X%.
7. **Replay-driven A/B** — every night, re-run today's tape with proposed param changes and compare PnL. Required for any "auto-tuning" claim to be honest.
8. **Anomaly detection on chain** — sudden vol-of-vol spike, IV skew dislocation, or one-sided OI build → auto-defensive mode.
9. **Operator playbook in code** — codify your current discretionary overrides (when do *you* manually pause? when do you bump max_lots?) as named "operator profiles" the bot can adopt under named regimes.
10. **State reconstruction from exchange truth** at startup — current bot trusts session storage; an institutional bot rebuilds from fills, then reconciles.

---

## Human Trader Edge Translation

A skilled discretionary trader does these things the bot does not:

| Human edge | Translatable rule |
|---|---|
| "Today's a chop day, I'm staying out." | Entry regime gate on RV/IV + ATR-percentile. |
| "Spread is too wide, I'll wait." | Microstructure depth + spread gate before any order. |
| "I just lost three in a row, I need to step back." | Account-level consecutive-loss cool-off. |
| "CPI is in 30 min, flatten." | Static event calendar → force flat / no-new-entries window. |
| "It's gone parabolic, I won't fade this." | Spot-velocity (ATR multiple per minute) → block adjustments on aggressor side; close-only mode. |
| "PnL is bad, I'll size down." | Daily-loss-aware sizing: scale `initial_lots` down by a factor of cumulative daily loss vs. budget. |
| "Premium I just collected isn't worth the gamma I'm taking." | Pre-trade EV check: `premium / (gamma_delta_at_2σ_move)` floor. |
| "I'm flat, I'm done, market doesn't owe me." | Profit-take rule — if session NetPnL ≥ X% of max_loss, force close + lock for day. |
| "Chain feels off." | Chain-anomaly detector (skew, OI shift, IV rank change). |
| "I'm overriding the system because I see something." | Trigger pin already does this; extend to "session-flat pin" and "no-replenish pin." |

---

## Institutional Roadmap

**Stage 1 — Truthful Operations (weeks)**
Fix VIPSO control plane. Wire margin API. Bid-ask + depth + quote-age gates. Slippage logging. Daily loss budget. Hard-stop / heartbeat tightening. `incomplete=True` halts adjustments.

**Stage 2 — Edge Measurement (1–2 months)**
Per-regime PnL attribution. Realized-vs-implied tracker. Entry regime gate. Replay infrastructure faithful to state progression (also a P0 of VIPSO). Counterfactual nightly runs for proposed params.

**Stage 3 — Greeks-Native (2–3 months)**
Replace USD-loss-driven hedging with delta/gamma/vega target hedging. Real perp delta hedge wired by default. Portfolio-level Greeks view across strategies. Vega budget per session.

**Stage 4 — Account & Execution (3–4 months)**
Account-level risk overlay across MMM + grid + reverse + manual. TWAP slicing for large sells. Smart routing across venues if applicable. Stress-test simulator (gap, vol spike, IV crush, halt).

**Stage 5 — Adaptive (6+ months)**
Online parameter suggestion (human-approved). Anomaly detector with auto-defensive mode. Codified operator playbooks. Self-replay learning loop with performance-attribution diffs published to dashboard.

**Stage 6 — Production-Hardened**
Three-region failover. Reconstruction-from-fills startup. Formal SLOs for heartbeat lag, fill confirmation, P&L freshness. Independent post-trade ledger reconciliation. Auditable risk decision log.

---

## Final Verdict

**This is a serious, hardened *execution* engine wrapped around a *naive* trading philosophy.** The defense layers are real; the offense layer is a 3-line assumption that "selling premium is edge." Every hard incident in the work log was a *plumbing* bug (stale generation, frozen-lots leak, gamma-block starvation, hedge-replenish gap) — not a *strategy* failure. That is partly because there is barely any strategy code to fail. The bot has nothing to say about whether today is a good day to sell premium.

You can keep this running profitably at small size with a smart operator (you) supplying the missing brain in real time. Scaling capital, removing the operator, or running multiple sessions in parallel will expose the gap fast — because the system has no concept of *cumulative risk*, *liquidity*, *regime appropriateness*, or *learning*.

The shortest path to "institutional" is unsexy: truth-up the VIPSO control plane, add microstructure and margin reality, install a daily/weekly loss budget, and wire one honest replay loop. Everything else (Greeks-native hedging, online tuning, portfolio overlay) is a months-long climb on top of that foundation, and is wasted effort if the foundation isn't honest first.

**Bottom line: the bot is a 6.5/10 execution engine attached to a 3/10 strategist. Fix the strategist before you scale the engine.**
