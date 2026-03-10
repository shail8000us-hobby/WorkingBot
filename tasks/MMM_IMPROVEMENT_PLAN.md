# MMM Improvement Plan — Full Analysis & Impact Guide

> **Date:** March 10, 2026
> **Author:** AI Analysis — Human approval required before any implementation
> **Source files analysed:**
> - `MMM_BUGS_AND_IMPROVEMENTS.md` — Live session post-mortem (session mmm26feb26-1)
> - `MMM_REMAINING_WORK.md` — Developer audit (P0/P1/P2/P3 backlog, as of Feb 27)
> - `MMM_SUGGESTION_SYSTEM_DESIGN.md` — New advisory system design
> - `AI_MMM_CONTEXT.md` — Ground truth of what is already implemented
> - `MMM_10_OF_10_PRODUCTION_PLAN.md` — Already 100% complete (do not repeat)
>
> **Rule:** This document is read-only for planning. No code is written here. Each section states the expected impact on the live algo with a concrete example, so you can judge whether the change is worth implementing.

---

## Quick Reference — What Is and Is Not Implemented

| Source | Item | Status |
|--------|------|--------|
| Session bugs BUG-1 to BUG-7 | Only summary table visible (detail text missing from file) | Unknown — verify before acting |
| IMP-2 Tiered trend guard | 4-tier system (0.5%/1.0%/1.5%/2.0%) | ✅ IMPLEMENTED (§2.12 of context) |
| IMP-3 Asymmetry hard block at 7:1 | Only 3:1 warn + 5:1 alert exist | ❌ PENDING |
| IMP-4 Strike shift lot reduction | No OTM-proximity scaling | ❌ PENDING |
| IMP-5 Consecutive same-direction limiter | Not in codebase | ❌ PENDING |
| IMP-6 Max loss scaling | Hard-coded, not position-scaled | ❌ PENDING |
| IMP-7 Options buyback capability | Algo cannot buy back CE/PE at all | ❌ PENDING (high effort) |
| IMP-8 Pre-entry regime check | No entry momentum check | ❌ PENDING |
| IMP-9 Full-delta perp when capped | Perp does incremental rebalancing only | ❌ PENDING |
| IMP-10 Cap raise risk acknowledgment | No warning when hot-reloading cap | ❌ PENDING |
| IMP-11 PE rebalancing (buyback) | No buyback tool at all | ❌ PENDING (same as IMP-7) |
| IMP-12 Both-sides-up Telegram alert | Telegram module exists but not called here | ❌ PENDING |
| IMP-13 Smarter whipsaw detection | Counts all alternations equally | ❌ PENDING |
| P1-A Safety checks fire 2-3x per beat | Deduplicated safety calls needed | ❌ PENDING |
| P1-B Reversal cooldown hardcoded | Must be configurable | ❌ PENDING |
| P1-C `_atm_wind_down_triggered` never cleared | Flag persists after close | ❌ PENDING |
| P1-D Partial fill not propagated | Position ledger gets wrong lot count | ❌ PENDING |
| P2-A mmm_monitor.py extraction | 5533-line god object | ❌ PENDING |
| P2-B Socket.IO room isolation | All clients get all sessions' events | ❌ PENDING |
| P2-C Missing test coverage | Initializer, executor, storage | ❌ PENDING |
| P2-D sort_keys checksum fix | Checksum fragile across runtimes | ❌ PENDING |
| P2-E Dead code cleanup | Tombstone comments, unused flags | ❌ PENDING |
| P3-1 to P3-15 | Backlog improvements | ❌ PENDING |
| Suggestion System | New `mmm_suggestions.py` module | ❌ PENDING (design only) |

---

## Section 1 — P1 Stability Bugs (Fix These First — They Affect Live Trading)

These four items are from `MMM_REMAINING_WORK.md`. They are confirmed bugs that can cause incorrect behaviour in a live session right now.

---

### P1-C: `_atm_wind_down_triggered` Never Cleared

**File:** `mmm_monitor.py`
**Risk level:** Medium
**Effort:** 1 hour

**What is happening now:**
When any original strike becomes ATM (BTC spot within 0.5% of entry strike), the monitor sets `session['_atm_wind_down_triggered'] = True` and switches to gradual LIFO buyback. This is correct.

The bug is: **after all positions close and the session is fully finished, the flag stays True forever in the session dict**. If you run a second entry round in the same session (e.g. you re-initialized), the ATM wind-down activates immediately at start — even though BTC is nowhere near ATM — because the flag from the previous round is still set.

**Concrete example:**
- Session starts, CE at 95000. BTC hits 94600 (0.4% away). Flag set. Wind-down runs. All positions close.
- You re-initialize the session with CE at 98000 and PE at 92000. BTC is at 95000 (3% away from both).
- On the first heartbeat, `is_wind_down_active()` sees `_atm_wind_down_triggered = True` and activates LIFO buyback immediately — even though no positions are ATM.
- **Result:** The new session starts in wind-down mode from beat 1. No new sells are allowed even though conditions are fine.

**Impact of fix:** Wind-down flag resets when all positions close, so re-initialization starts clean. Zero impact on the normal single-session flow.

---

### P1-B: Reversal Cooldown Duration Is Hardcoded

**File:** `mmm_reversal.py`
**Risk level:** Low
**Effort:** 2 hours

**What is happening now:**
After a reversal is detected (e.g. CE was aggressor, now PE is aggressor), the cooldown period is always `adjustment_interval × 2`. This is not configurable.

**Concrete example:**
- You set `adjustment_interval = 3600s` (1 hour) because you want a slow-paced session on a calm expiry day.
- A reversal fires at 10:00.
- Cooldown = 3600 × 2 = **7200 seconds = 2 hours**.
- By 12:00, the session has done nothing for 2 hours even though premiums may be moving.
- You cannot fix this without also reducing `adjustment_interval`, which changes the entire session pace just to fix the cooldown.

**Impact of fix:** A new `reversal_cooldown_seconds` parameter (default 0 = use legacy formula) lets you set the cooldown independently. For example `reversal_cooldown_seconds = 600` gives a 10-minute cooldown regardless of heartbeat speed. Backward compatible — default 0 preserves old behavior exactly.

---

### P1-A: Safety Checks Fire 2–3 Times Per Degraded Heartbeat

**File:** `mmm_monitor.py` (~lines 841–851 and 1092–1096)
**Risk level:** Low
**Effort:** 2–3 hours

**What is happening now:**
`run_all_checks()` is called in three separate code paths: normal beat, miss beat (exchange API slow), and partial beat (circuit breaker OPEN). In a degraded network scenario, all three paths can execute, meaning safety checks run 2–3 times in a single heartbeat cycle.

**Concrete example:**
- Exchange API is slow. Both the "miss beat" and "partial beat" code paths trigger.
- `check_trailing_stop()` fires twice.
- The trailing stop `peak_pnl` updates twice in one cycle with slightly different values (the second call reads the modified `peak_pnl` from the first call).
- **Result:** Spurious safety alert fires ("P&L dropped 50% below peak") even though the session is fine — just the API was slow for one beat. Session auto-pauses incorrectly.

**Impact of fix:** Safety checks run exactly once per beat regardless of which code path is taken. Fewer false safety pauses during network degradation, which matters during volatile BTC markets when exchanges are most likely to have API hiccups.

---

### P1-D: Partial Fill Not Propagated to Position Ledger

**Files:** `mmm_executor.py` → `mmm_engine.py`, `mmm_wind_down.py`, `mmm_close_at_5.py`
**Risk level:** Medium
**Effort:** 3–4 hours

**What is happening now:**
When `smart_execute()` places an order and the exchange only fills part of it (e.g. you asked for 50 lots but only 30 traded), the callers in `mmm_engine.py` and `mmm_close_at_5.py` trust the request size (50) rather than the actual filled size (30). The position ledger records 50 lots even though you only sold 30.

**Concrete example:**
- Adjustment fires. Algo wants to sell 50 PE at strike 94000 at $120.
- Exchange is illiquid. Only 30 lots fill in 60 seconds. Order times out.
- `smart_execute()` returns `filled_size = 30`.
- Caller in `mmm_engine.py` records the position as 50 lots, not 30.
- Internal state: 50 PE lots at 94000.
- Exchange reality: 30 PE lots at 94000.
- **Consequence:** P&L calculations are wrong. Next trigger evaluation is wrong. On close-at-5, the buyback order is sized for 50 lots but only 30 exist — the exchange returns an error.
- In the worst case, the algo thinks it has more hedge coverage than it does, leading to under-hedging on the next CE move.

**Impact of fix:** Position ledger uses `filled_size` from the executor response, not the requested size. State accurately reflects reality. Adds a warning log when partial fills occur so you can investigate liquidity.

---

## Section 2 — Profitability Improvements from Session Post-Mortem

These are from `MMM_BUGS_AND_IMPROVEMENTS.md`, based on analysis of a real session (mmm26feb26-1) where CE went from $107 to $724 in a single expiry.

**Important note on IMP-1:**
The document file starts mid-paragraph at "The deeper insight:" — the full description of IMPROVEMENT-1 ("Lot sizing compounding formula") and BUG-1 through BUG-7 detail sections are missing from the file (only their summary table rows exist). Do not implement IMP-1 until you locate the full description.

---

### IMP-3: Asymmetry Hard Block at 7:1 (High Impact, Low Effort)

**Files:** `mmm_safety.py`
**Risk level:** Low
**Effort:** Half a day

**Current behavior:**
The asymmetry check has two levels:
- 3:1 ratio: "Warning, continue"
- 5:1 ratio: "Alert, warn"
Neither blocks selling.

**What happened in the session:**
CE stayed at 132 lots. PE grew to 700 lots = a **5.3:1 ratio**. The 5:1 alert fired but did not stop PE selling. The session kept adding PE, which collected no additional meaningful coverage for CE — it just built a large one-sided book. When BTC eventually reversed, the 700 PE lots created massive margin requirements and a different catastrophic risk.

**Proposed new tier:**

| Ratio | Level | Action |
|-------|-------|--------|
| 3:1 | Warning | Log, continue (existing) |
| 5:1 | Alert | Reduce next lot size by 50% (new behaviour at this tier) |
| 7:1 | Hard Stop | Block ALL new sells on the heavier side |

**Concrete example of the fix in action:**
- CE at 132 lots, PE at 900 lots = 6.8:1. Next heartbeat, PE is aggressor again.
- Algo calculates 40 new PE lots to sell.
- New 5:1 tier: 40 × 0.5 = **max 20 lots this adjustment**.
- Ratio reaches 7:1 (CE: 132, PE: 950). Hard block fires.
- No more PE sells until the ratio drops below 7:1 — either by buying back PE or selling CE.
- **Result:** Asymmetry is capped. Margin requirement is capped. Tail risk on a BTC reversal is capped.

**Risk of implementing:** Very low. This is an additive safety check. It only activates at extreme imbalance (7:1) that is already dangerous. No impact on normal sessions where ratios stay below 5:1.

---

### IMP-4: Strike Shift Lot Reduction (High Impact, Medium Effort)

**Files:** `mmm_engine.py` (lot calculation), `mmm_strike_shift.py`
**Risk level:** Medium
**Effort:** 1 day

**Current behavior:**
When the algo shifts to a new (closer to ATM) strike, it calculates lots using the standard formula: `N = ceil(loss / premium × (1 + buffer))`. This is purely based on premium, not on how close the new strike is to spot.

**The problem:**
A closer-to-ATM strike has higher delta per lot. Selling the same number of lots as a farther OTM strike means taking on much more directional risk per unit of hedge collected.

**Concrete example:**
- PE first shift: Strike 64400 (BTC at ~66000) = 2.4% OTM. Delta per lot ≈ 0.20.
- PE second shift: Strike 65400 (BTC at ~67000) = 2.4% OTM again but higher premium decayed faster. Delta per lot ≈ 0.35.
- Formula says sell 88 lots at 65400.
- Portfolio PE-side delta = 88 × 0.35 = **30.8 BTC**.
- If BTC falls $1,000, delta-driven PE loss ≈ $30,800 before gamma even kicks in.
- For comparison, at the original 63200 strike (5% OTM), 88 lots × delta 0.08 = **7 BTC delta** — 4.4× less dangerous.

**Proposed lot reduction by OTM distance:**

| New strike OTM distance | Multiplier applied to calculated lots |
|------------------------|---------------------------------------|
| > 3% OTM | 1.0 (no change — same formula as always) |
| 2% – 3% OTM | 0.75 |
| 1% – 2% OTM | 0.50 |
| < 1% OTM | 0.25 (near ATM — be conservative) |

**Example with fix:**
- Strike 65400 is 2.4% OTM → multiplier 0.75
- Formula says 88 lots → 88 × 0.75 = **66 lots**
- Portfolio delta = 66 × 0.35 = 23.1 BTC (vs 30.8 before) — still high, but more controlled
- Near-expiry shift to 67000 (1.0% OTM): 88 × 0.25 = **22 lots** — dramatic risk reduction

**Parameters to add:** `strike_shift_use_lot_scaling` (bool, default False), `strike_shift_otm_thresholds` (configurable percentages), `strike_shift_multipliers`.

**Risk:** Medium. The formula change reduces the hedge collected per shift — so CE losses are slightly less covered per adjustment. The tradeoff: less coverage per adjustment but dramatically less gamma risk. The perp hedge can fill the remaining delta gap.

---

### IMP-5: Consecutive Same-Direction Adjustment Limiter (Highest ROI Change)

**Files:** `mmm_engine.py`, `mmm_state.py` (new param + counter)
**Risk level:** Medium
**Effort:** 1 day

**Current behavior:**
The whipsaw check counts *alternating* adjustments (CE then PE then CE). There is **no check for runs** — consecutive same-direction adjustments (CE 5 times in a row).

**What happened in the session:**
Adjustments #3, #4, #6, #7, #8, #9, #10, #11 were all CE aggressor (PE hedge). That is 8 consecutive adjustments in one direction. The algo's formula treated each as an independent event and calculated lots fresh each time, leading to explosive PE accumulation.

**Proposed rule:**
After 3 consecutive same-direction adjustments, cap the lot size for that direction at `initial_lots × 0.25`.
After 5 consecutive same-direction adjustments, require a force-heartbeat manual confirmation before any further sells in that direction.

**Concrete example:**
Session has `initial_lots = 100`. BTC in a bull run.

- Adj #1 (CE aggressor): formula says 71 PE lots → **71 lots sold** (counter = 1)
- Adj #2 (CE aggressor): formula says 54 PE lots → **54 lots sold** (counter = 2)
- Adj #3 (CE aggressor): formula says 48 PE lots → **cap kicks in: min(48, 100×0.25=25) → 25 lots sold** (counter = 3)
- Adj #4 (CE aggressor): formula says 60 PE lots → **25 lots sold** (counter = 4)
- Adj #5 (CE aggressor): **BLOCK — requires force heartbeat confirmation** (counter = 5)

Without the fix: After 8 adjustments, PE = 132 + 71 + 54 + 48 + 34 + 45 + 88 + 75 = **547 lots** accumulated. Cap hit.
With the fix: After 8 adjustments, PE = 132 + 71 + 54 + **25 + 25 + BLOCKED** = **307 lots maximum** before the manual gate fires.

**Impact:** The post-mortem document calls this "the single most profitable change." It does not eliminate the session loss — but it slows accumulation so there is still hedge capacity available when BTC eventually moves the other way. Lower accumulation per session × more sessions that survive = better long-term P&L.

**Parameters to add:** `consecutive_dir_limit` (default 3), `consecutive_dir_lot_cap_pct` (default 0.25), `consecutive_dir_block_after` (default 5).

---

### IMP-12: Both-Sides-Up Telegram Notification (Quick Win, Low Effort)

**Files:** `mmm_monitor.py`, `mmm_telegram.py`
**Risk level:** Very low
**Effort:** 1–2 hours

**Current behavior:**
When both CE and PE exceed their triggers simultaneously (`BOTH_SIDES_UP`), the algo pauses and logs it. The WebUI shows an alert modal — but only if you are watching the UI. No push notification is sent.

**The problem:**
Both-sides-up is the most dangerous state. It means the market has moved against both legs simultaneously. This requires human judgment within minutes. If you are not watching the dashboard (sleeping, away from desk), you will not know until you check.

**The fix:**
Call `mmm_telegram.py`'s Telegram alert function immediately when `BOTH_SIDES_UP` is set. The Telegram module already exists and is already used for margin tier alerts.

**Concrete example:**
- 3:00 AM IST. BTC flash crash + recovery. Both CE ($420) and PE ($380) above triggers simultaneously.
- Without fix: Dashboard shows alert. You are asleep. Session sits paused for 5 hours.
- With fix: Telegram message arrives: "🚨 BOTH SIDES UP — CE $420 / PE $380. Session paused. Manual decision required."
- You see it at 5:00 AM and act within minutes, not after 5 hours of sitting.

**Risk:** Zero. The Telegram module is already tested and live. This is a single function call addition.

---

### IMP-6: Max Loss Should Scale With Position Size

**Files:** `mmm_config.py`, `mmm_safety.py` (validation + suggestion)
**Risk level:** Low
**Effort:** 2–3 hours

**Current behavior:**
`max_loss_amount` defaults to $5,000 and is set as an absolute dollar number. There is no relationship to position size.

**The problem:**
A 100-lot session collecting $207 total premium has a natural P&L range of several thousand dollars just from spread alone. A $5,000 stop on a session that eventually grows to 800 lots (as happened in the post-mortem session) is equivalent to a 0.6% stop — nearly guaranteed to be triggered by noise.

**Proposed formula for the suggested minimum:**
`suggested_min = initial_lots × total_net_premium_per_lot × 0.50`

For the post-mortem session: 100 lots × $207 premium × 0.50 = **$10,350 minimum**. The default $5,000 was half what was needed.

**The fix has two parts:**

1. **Validation warning:** When a session is initialized, calculate the suggested minimum and warn if `max_loss_amount < suggested_min`. The warning shows: "Your max_loss_amount ($5,000) is below the suggested minimum ($10,350) for this position size. Consider raising it."

2. **Suggestion system integration (see Section 4):** If `max_loss_amount < suggested_min` at any point, generate a medium-priority suggestion with the calculated value.

**Risk:** Very low. This adds a warning/validation, not a behavior change. The existing max_loss check is unchanged. The user still sets the number.

---

### IMP-9: Full Portfolio Delta Hedge When Position Cap Is Hit

**Files:** `mmm_perp_hedge.py`
**Risk level:** Medium
**Effort:** 1 day

**Current behavior:**
The perp hedge runs in "incremental rebalancing" mode: if portfolio delta drifts beyond the band (0.005 BTC), it executes a small trade to bring delta back to zero. It never looks at the total portfolio delta — only the change.

**The problem:**
When the PE position cap is hit and BTC keeps rising, the short CE lots accumulate a growing negative delta. The perp hedge is only rebalancing the small drift — not the full exposure.

**Concrete example:**
- PE cap hit at 500 lots. 132 short CE lots remain.
- BTC rises another 5%. CE premium goes from $418 to $724.
- CE delta at $724 ≈ 0.85 per lot × 132 lots = **112 BTC of negative delta**.
- Perp hedge (incremental mode) is making tiny 0.5–1.0 BTC adjustments.
- **Net portfolio delta is still ~-110 BTC** despite the perp being "active."

**The fix:**
When `_position_cap_hit == True` (a flag set when M2 recycler can't free space), switch the perp to **full portfolio delta mode**:
- Calculate total portfolio delta across ALL positions (CE + PE + existing perp).
- Target: net delta = 0.
- Execute a single properly-sized perp trade.
- Example: If total delta = -112 BTC, buy 112 BTC worth of perp.
- Maintain this until either the cap is cleared or the session ends.

**Impact:** Provides meaningful protection during the most dangerous phase of a session — when both the option cap is hit AND the market is still trending. This would have significantly reduced the post-mortem session's unrealized loss during the 14:00–15:30 cap period.

**Risk:** Medium. The perp can get very large in full delta mode. Need a `perp_full_delta_max_lots` cap to prevent margin exhaustion from the perp itself. Default: `min(perp_hedge_max_lots, 3 × initial_lots)`.

---

### IMP-10: Cap Raise Risk Acknowledgment Dialog

**Files:** `mmm_api.py` (hot-reload endpoint), `MMMSettingsDialog.js`
**Risk level:** Low
**Effort:** Half a day

**Current behavior:**
When you hot-reload `max_lots_per_side` to a higher value, the change applies immediately with no warning. The UI shows the new value.

**What happened in the post-mortem session:**
The cap was raised from 300 → 500 → 700 → 1000 in three consecutive hot-reloads during a crisis. Each raise was a desperate response to CE rising, but it did not reduce CE exposure — it just allowed more PE to be added. The operator was chasing the loss with more lots.

**Proposed change:**
When `max_lots_per_side` is increased via hot-reload, the backend calculates and returns an impact preview before applying the change:

```
⚠️ Cap Raise Impact:
  Current CE unrealized loss: ~$8,200
  New max PE lots allowed: 500 (was 300)
  If next adjustment fully utilizes new capacity: PE total = 520 lots
  CE/PE asymmetry after cap raise: 3.9:1
  Note: Raising PE cap does not reduce CE exposure.
  [CONFIRM RAISE] [CANCEL]
```

**Effect:** Forces the operator to consciously see that raising PE cap does nothing for CE. The confirmation dialog provides a "reality check" moment. The change is still applied if confirmed — it is not blocked, just acknowledged.

**Risk:** Very low. The calculation is straightforward (already-available data). The confirmation only delays the change by one click.

---

### IMP-8: Pre-Entry Regime Check (Moderate Effort, High Value)

**Files:** `mmm_initializer.py`, `mmm_state.py`, UI entry form
**Risk level:** Low
**Effort:** 1 day

**Current behavior:**
When you start a session (Mode A — Fresh), the algo immediately initializes and starts the heartbeat. No check is done on whether current market conditions are suitable for entering a short strangle.

**What happened in the post-mortem session:**
The session started at 12:02 UTC. The **first adjustment fired at 12:07** — 5 minutes after entry. This means the market was already moving at the moment of entry. Ideal entry for a short strangle is a range-bound, low-momentum market.

**Proposed pre-entry checks (shown to user as warnings, not hard blocks):**

| Check | Condition | Warning shown |
|-------|-----------|---------------|
| 1 Momentum | BTC moved > 0.5% in last 10 min | "BTC moved 0.7% in last 10 min. Market has momentum. Consider waiting for calmer conditions." |
| 2 Strangle width | Strikes not equidistant from spot | "CE is 2.9% OTM but PE is 2.1% OTM. Consider symmetric strikes for delta neutrality." |
| 3 Session time | Entry < 30 min after exchange open | "Entering within 30 minutes of market open. Price discovery may cause early adjustments." |
| 4 Remaining expiry | Entry < 2 hours to expiry | "Only 1.5 hours to expiry. Wind-down will activate almost immediately." |

**These are warnings only, not blocks.** The user can still enter. The warnings appear on the entry confirmation screen.

**Risk:** Very low. Purely informational. No trading logic changes.

---

## Section 3 — Pending P2 Quality Items

These do not affect trading correctness but affect maintainability and reliability.

### P2-D: sort_keys Checksum (15 minutes — do this immediately)

**File:** `mmm_storage.py`
**Current:** `json.dumps(data, default=str)` — dict key order is Python 3.7+ insertion-ordered but can differ between restarts.
**Fix:** `json.dumps(data, sort_keys=True, default=str)` — checksum is now deterministic across restarts.
**Impact:** Eliminates rare "checksum mismatch" false alarms that currently auto-pause the session on restart.

---

### P2-E: Dead Code Cleanup (2 hours)

Items to remove from `mmm_monitor.py`:
- Tombstone comment about "proactive wind-down" (~line 1052) — git preserves history
- `_force_event = threading.Event()` — set in `__init__` but `.set()` is never called anywhere

Items to audit in `mmm_state.py`:
- `close_5_enabled` — check if still read; may be superseded by `close_at_threshold`
- `enable_reversal` — if always True everywhere, remove the flag check
- `perp_hedge_*` params present even in non-perp sessions — these are low-noise but waste memory per session

**Impact:** Reduces cognitive load when reading `mmm_monitor.py`. No trading impact.

---

### P2-B: Socket.IO Room Isolation (3–4 hours)

**Current:** Every heartbeat from every active session is broadcast to every connected WebUI client. If you have 5 sessions running, a single browser tab processes 5× the heartbeat events.
**Fix:** Emit each session's events only to clients that have joined that session's room.
**Impact:** Reduces frontend CPU load. More important as session count grows. Requires coordinated frontend + backend change — deploy both together.

---

### P2-A: Monitor God Object Extraction (Phase 1 only: 2 hours)

**File:** `mmm_monitor.py` is 5,533 lines. The recommended first extraction is `_finalize_heartbeat()` — the "cleanup before return" pattern that appears 5+ identical times in the heartbeat loop.
**Impact:** Makes the heartbeat loop 30–50 lines shorter. Makes it easier to add future features without copy-pasting the cleanup block.
**Do not attempt full extraction** — the architectural review required for that is a separate weeks-long project.

---

## Section 4 — Suggestion System (New Feature: mmm_suggestions.py)

This is a **new module design** from `MMM_SUGGESTION_SYSTEM_DESIGN.md`. It is a non-invasive advisory layer.

**Core principle:** The system observes the running session every heartbeat and generates human-readable advisory cards shown in the WebUI. It never auto-executes anything. Every suggestion has a "Dismiss" button and (for param changes) an "Apply" button.

### What It Does

Every heartbeat, after all safety/trigger/adjustment logic runs, a new function `evaluate_all(context)` in `mmm_suggestions.py` looks at the session state and generates a list of `Suggestion` objects. These are sent to the frontend via a new WebSocket event `mmm_suggestions` and displayed as a collapsible card list.

**18 rules across 4 categories:**

| Category | Rules | Examples |
|----------|-------|---------|
| Risk Warnings | RW-01 to RW-05 | Total exposure at 85%+, P&L approaching max loss, margin YELLOW for 3+ beats |
| Parameter Tuning | PT-01 to PT-06 | Enable shift_recycle, lower harvest threshold, enable wind-down near expiry |
| Market Behavior | MB-01 to MB-05 | IV spike with regime off, BTC approaching entry strike, expiry in < 30 min |
| Opportunity Alerts | OA-01 to OA-04 | Frozen position decayed to $3, profitable cleanup available |

### Impact Example — Rule RW-03

**Without suggestion system:**
CE side has 60 frozen vs 30 active lots. The operator looks at the dashboard and sees lots numbers. They may not notice the imbalance or know what to do.

**With suggestion system:**
A high-priority card appears:
> ⚠️ HIGH — CE Frozen Baggage 2:1
> CE side has 60 frozen vs 30 active lots. Frozen positions are consuming capacity that could be used for hedging. Options: (1) Enable shift_recycle to auto-clean during next strike shift, or (2) manually close cheap frozen positions.
> [Apply: Enable shift_recycle] [Dismiss]

The operator sees this immediately and can act with one click.

### Impact Example — Rule MB-03

**Without suggestion system:**
BTC spot is $69,200. CE entry strike was $69,600. The operator may not notice the 0.6% proximity.

**With suggestion system:**
> ⚠️ HIGH — BTC Approaching CE Strike
> BTC ($69,200) is 0.6% from your CE entry strike ($69,600). ATM gamma risk is elevated. If BTC reaches $69,600, CE premium will accelerate rapidly. Consider: (1) Enable wind_down_on_atm, or (2) Reduce CE lots now.
> [Apply: Enable wind_down_on_atm] [Dismiss]

### Why This Is Low Risk to Implement

The entire suggestion system is a **pure read-only analysis layer**. It reads session state, premiums, margin, regime — all already available in the heartbeat context. It does not call any exchange API. It does not modify any session state. The "Apply" button for param changes calls the existing hot-reload endpoint — no new execution paths. If the module crashes, the rest of the heartbeat is unaffected (it runs in a try/except block at the end).

### Implementation Order (as designed)

1. Phase 1: Core infrastructure — `mmm_suggestions.py`, `emit_suggestions()`, `MMMSuggestionPanel.js` + 3 API endpoints (get/apply/dismiss) — 1 day
2. Phase 2: Risk warning rules (RW-01 to RW-05) — half day (highest value)
3. Phase 3: Market behavior rules (MB-01 to MB-05) — half day
4. Phase 4: Parameter tuning + opportunity rules — half day
5. Phase 5: Cooldowns, dismissed state persistence, Telegram for critical — half day

**Total: 3 days for a complete suggestion system.**

---

## Section 5 — P3 Backlog (No Rush — Do When Time Permits)

Brief summary of the 15 P3 items. None affect trading correctness.

| # | What | Value | Effort |
|---|------|-------|--------|
| P3-2 | Dry-run / paper trading mode | Very high for CI testing | 1 day |
| P3-5 | Watchdog sends Telegram on restart | High — operators currently have no out-of-band notification when the monitor crashes and auto-restarts | 1 hour |
| P3-1 | Structured JSON logging | High for debugging post-crash | 2 days |
| P3-3 | `validate_session()` integrity check | Medium | Half day |
| P3-4 | `clear_stale_snapshots()` for trigger dict | Medium | Half day |
| P3-6 | Frontend session Map instead of array | Low/Medium | 1 hour |
| P3-7 | `HeartbeatPayload` dataclass | Code clarity | Half day |
| P3-8 | SQLite connection pooling | Performance | Half day |
| P3-9 | Cache `is_wind_down_active()` per beat | Micro-optimization | 30 min |
| P3-10 | React Error Boundary in MMMContext | UI resilience | 1 hour |
| P3-11 | `compact_old_sessions()` | DB grows unbounded | 1 hour |
| P3-12 | Watchdog dynamic check interval | Faster detection for rapid sessions | 1 hour |
| P3-13 | Restart count persistence across restarts | Accurate max-restart protection | 1 hour |
| P3-14 | `get_activity_by_id()` indexed | Frontend performance | 1 hour |
| P3-15 | Adaptive dedup interval per activity type | Regime events currently too noisy in activity feed | 1 hour |

---

## Section 6 — What Remains Unknown (Verify Before Acting)

The `MMM_BUGS_AND_IMPROVEMENTS.md` file is **missing its opening content**. The file begins mid-paragraph at "The deeper insight:" which is clearly the tail end of IMPROVEMENT-1's description. BUG-1 through BUG-7 are listed in the summary table but their detailed descriptions are absent.

Before implementing IMP-1 or BUG-1 through BUG-7:
- Locate the original source of the full document (possibly a prior AI conversation or a backup)
- Or re-analyze a live session log to reconstruct what those bugs describe

**IMP-1 from the summary table:** "Lot sizing compounding formula — Critical — Design — High complexity." This is described as the most complex item. Do not implement it without the full specification.

---

## Recommended Execution Order

### Week 1 — Quick Wins + Stability (days 1–5)
1. **P2-D** sort_keys checksum (15 min) — zero risk
2. **P1-C** ATM wind-down flag never cleared (1 hour) — very low risk
3. **IMP-12** Both-sides-up Telegram notification (2 hours) — zero risk
4. **P1-B** Reversal cooldown configurable (2 hours) — very low risk
5. **IMP-10** Cap raise risk acknowledgment (half day) — very low risk
6. **IMP-6** Max loss scaling warning (half day) — very low risk
7. **P1-A** Safety checks deduplication (3 hours) — low risk

### Week 2 — High-Impact Trading Logic (days 6–10)
8. **P1-D** Partial fill propagation (4 hours) — medium risk, test thoroughly
9. **IMP-3** Asymmetry hard block at 7:1 (half day) — low risk
10. **IMP-5** Consecutive same-direction limiter (1 day) — medium risk
11. **IMP-8** Pre-entry regime check warnings (1 day) — low risk

### Week 3 — Complex Features (days 11–15)
12. **IMP-4** Strike shift lot reduction by OTM% (1 day) — medium risk
13. **IMP-9** Full-delta perp hedge when cap hit (1 day) — medium risk
14. **Suggestion System Phase 1+2** (2 days) — low risk

### Week 4 — Polish + Backlog
15. **Suggestion System Phase 3+4+5** (2 days)
16. **P2-E** Dead code cleanup (2 hours)
17. **P2-A** Monitor extract `_finalize_heartbeat()` (2 hours)
18. **P2-B** Socket.IO room isolation (4 hours) — deploy frontend + backend together
19. **P3 items** as time permits (P3-2, P3-5, P3-1 first)

---

## CRITICAL: Things to Never Touch Without Extensive Testing

From `MMM_REMAINING_WORK.md` — these paths have caused production issues before:

1. `mmm_engine.py` — `calculate_standard_loss()` and `calculate_reversal_loss()` — drive ALL adjustment decisions
2. `mmm_trigger.py` — `evaluate_triggers()` — THE core decision gate
3. `mmm_state.py` — `recompute_side_lots()` — rebuilds all derived state
4. `mmm_executor.py` — `smart_execute()` — places real exchange orders
5. `mmm_monitor.py` — the heartbeat loop — any refactor must be tested against all 5 beat paths

---

*This document is for planning and review only. Confirm each section before asking for implementation. Start with Section 1 (P1 stability) and the quick wins at the top of Week 1.*
