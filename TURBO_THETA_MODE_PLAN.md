# MMM Turbo Theta Mode — Honest Analysis & Implementation Plan

> **Author:** AI Analysis  
> **Date:** February 27, 2026  
> **Status:** Planning / Pre-implementation  
> **Verdict:** The idea has genuine merit — but in a narrower, more specific form than "turbo theta engine." See §2 for the honest assessment before reading the plan.

---

## 1. WHAT ARE WE EVALUATING?

A "Turbo Mode" that activates in the last few hours of 0DTE (zero-days-to-expiry) and acts as a **theta engine** — aggressively harvesting time decay as options collapse toward zero. Constraints:
- Same MMM calculations, no changes to core logic
- Must not affect existing MMM algo when turbo is NOT active
- The system is BTC 0DTE short-premium selling on Delta Exchange

---

## 2. HONEST ASSESSMENT — IS THIS A GOOD IDEA?

### 2.1 What Already Exists (Don't Reinvent)

Before designing anything new, it's important to acknowledge that the current MMM already has meaningful late-expiry behavior:

| Existing Feature | What It Does | Coverage |
|-----------------|--------------|----------|
| Wind-Down Mode (§2.11) | LIFO buyback at elevated threshold when ≤ 120 min to expiry | Partial theta harvest |
| Theta Acceleration (§2.8) | Widens triggers near expiry (`min(base × 2, 80)`) so short-lived premium moves don't trigger expensive adjustments | Lets theta work |
| Adaptive Interval (§2.10) | Drops to 60s when ≥80% of trigger exceeded | Fast monitoring |
| stop_adjustment_mins = 15 | Stops all new sells in final 15 min | Safety exit |
| auto_close_mins = 5 | Force-closes everything at 5 min remaining | Hard exit |
| Perp Hedge (§2.16) | Manages delta continuously, including near expiry | Gamma mitigation |
| Regime Tier 4 (§2.12) | Auto-triggers wind-down on 2% BTC move | Trend protection |

**The current system is already partially a "theta engine."** Theta acceleration + wider triggers + wind-down + LIFO closing is a coherent late-day philosophy. This is not a blank slate.

### 2.2 The Core Tension — Theta vs Gamma in Last 2 Hours

This is the critical physics you cannot escape:

**Theta and gamma are two sides of the same coin near expiry.** They cannot be decoupled:

- **Theta (your friend):** In last 2 hours of 0DTE, theta accelerates massively. An OTM option at $30 can go to $5 in 90 minutes purely from time decay — without BTC moving at all.
- **Gamma (your enemy):** In those same 2 hours, gamma for near-ATM options is at its absolute peak. A 0.5% BTC move near your strike can take that $30 option to $100+ in minutes.

**The trap:** You want to stay in positions to harvest theta. But the very force that makes theta valuable also makes gamma catastrophic. Near expiry, a BTC whipsaw of 0.8-1% can more than wipe out an entire day's theta harvest on that side.

**Verdict on "sell more near expiry" style turbo mode:**  
**This is a bad idea.** Selling new short option positions in the last 90-120 minutes of 0DTE means:
1. Bid-ask spreads are widest at this time (market makers widen for gamma risk)
2. Liquidity thins dramatically (hard to buy back at decent prices if things go wrong)
3. You have almost no time to execute adjustments if the move goes against you
4. Gamma can overwhelm MMM's adjustment formula since premiums spike too fast for even a 60-second heartbeat to catch

**This specific interpretation of "turbo" should be dropped.**

### 2.3 The Legitimate Gap — What "Turbo" COULD Mean

There IS a genuine gap in the current system that a well-designed turbo mode can fill:

**The gap:** The current wind-down mode is a **risk-reduction** mechanism (get out safely before expiry). What doesn't exist is a **theta maximization** mode that deliberately holds positions open LONGER in the last phase to collect more decay, while actively managing gamma risk through the perp hedge and smart closing logic.

Specifically:

| Current Wind-Down Behavior | What's Missing |
|---------------------------|---------------|
| Closes at `entry × 25%` threshold (e.g., sold at 100 → close at 25) | No time-ladder escalation of close threshold |
| LIFO order (most recently added first) | No gamma-priority ordering (ATM positions carry most gamma and should close first) |
| Static elevated threshold during entire wind-down window | Threshold should tighten progressively as expiry approaches |
| Perp hedge enabled/disabled globally | No "lock perp hedge ON" when turbo active to ensure gamma always covered |
| Adjustments may still run in wind-down if `floor_action ≠ stop_adjustments` | No clear "NO NEW SELLS AT ALL" guarantee in theta harvest phase |

---

## 3. THE GENUINE IDEA — "THETA SPRINT MODE"

Rather than a vague "turbo mode," it's better to define this as **Theta Sprint Mode**: a structured, time-gated phase that activates AFTER wind-down mode and runs closer to expiry. It is not a replacement for wind-down; it is the final phase AFTER wind-down.

### 3.1 Conceptual Timeline

```
Session Start (e.g., 9:30 AM)
│
│  ← Normal MMM: Full adjustment cycle, trigger evaluation, sells, regime controls
│
├── [-120 min] Wind-Down Activates
│     LIFO closes, elevated threshold (25% of entry), adjustments may be blocked
│     Selling is restricted but perp hedge still runs
│
├── [-60 min] Theta Sprint Activates  ← NEW
│     • HARD block on ALL new sells (no exceptions, no adjustments)
│     • Time-ladder close threshold: escalates every 15 min
│     • Gamma-priority position ordering (ATM/nearest-to-spot closes first)
│     • Perp hedge LOCKED ON (cannot be disabled while sprint active)
│     • Heartbeat interval pinned at 30s (faster than current 60s minimum)
│     • Sprint-specific WebSocket event for UI badge
│
├── [-15 min] stop_adjustment_mins (existing, unchanged)
│
├── [-5 min] auto_close_mins (existing, unchanged)
│
└── Expiry
```

### 3.2 What Theta Sprint Does Differently

**Feature 1 — Time-Ladder Close Thresholds**

Instead of wind-down's static `entry × 25%` threshold, Theta Sprint escalates the close trigger as expiry approaches:

```
[-60 to -45 min]:  close if premium ≤ entry × 20%
[-45 to -30 min]:  close if premium ≤ entry × 30%
[-30 to -20 min]:  close if premium ≤ entry × 40%
[-20 to -10 min]:  close if premium ≤ max(entry × 60%, 8)
[-10 to -5  min]:  close if premium ≤ max(entry × 80%, 5)
```

The effect: positions that are still at elevated premiums (because BTC didn't move) are allowed to decay further. Positions near zero get closed early. As time runs out, the "acceptable minimum" rises, so everything closes.

**Why this is better than static 25%:** A position entered at premium 80 might be at premium 16 (20% of entry) at -60 min. Static wind-down says: don't close yet (16 > 80×0.25=20). Time-ladder says: close it now at -60 min (20% rule). This captures the position while markets are still liquid.

**Feature 2 — Gamma-Priority Position Ordering**

Current LIFO ordering closes newest positions first (most recent adjustment fills). Theta Sprint should close by gamma exposure instead:

```
Priority Order:
1. Positions at strikes closest to current spot (highest gamma, highest risk)
2. Positions at strikes furthest from current spot (low gamma, can afford to wait longer)
```

This means: near-the-money positions get closed first even if they were opened first. OTM positions that are quietly decaying toward zero get to keep running.

**Why this matters:** In the last hour, your biggest gamma risk comes from positions that are near ATM. Closing those first reduces your most dangerous exposure. Your far-OTM positions are the "safe theta harvest" — they can run longer.

**Feature 3 — Hard NO-SELL Lock**

During Theta Sprint, there are ZERO new sell orders. Not "adjustments are discouraged" — literally `SELL_BLOCKED = True` at the session level. This is different from `wind_down_floor_action=stop_adjustments` which only activates when the floor is reached.

The logic: in the last 60 minutes of 0DTE, the risk-reward of opening new shorts is deeply unfavorable. You're collecting 10-20 USDT of premium for gamma risk that could spike to 200+ on a BTC move. This is a bad trade. The perp hedge is the only tool that should still be operating on the delta dimension.

**Feature 4 — Perp Hedge Locked ON**

If Theta Sprint is active, `perp_hedge_enabled` is force-overridden to `True` for the duration of the sprint (if perp hedge is configured). The rationale: you've blocked all selling. Your only defense against directional moves is the perp hedge. Taking it offline during the most gamma-intensive phase is risky.

This does NOT change perp hedge parameters. It simply ensures it cannot be toggled off accidentally or by a stale UI action when you're in the last hour.

**Feature 5 — 30-Second Heartbeat Pinned**

The current minimum interval is 60 seconds. In the last 60 minutes of 0DTE, 60 seconds is too slow. A BTC move that takes a $20 option to $45 in 45 seconds is a real scenario near expiry.

Theta Sprint pins the heartbeat at 30 seconds. This is only active during the sprint window (last 60 min), so it doesn't waste resources earlier in the day.

NOTE: This is not "check every 30s and try to sell." There are no sells. It's "check every 30s to see if any position has hit its time-ladder close threshold" and to update perp hedge delta.

---

## 4. MY SUGGESTED IMPROVEMENTS

### 4.1 Sprint Activation Window Should Be Configurable

Don't hardcode 60 minutes. Some traders may want to start the sprint at 90 min, others at 45 min. Parameter: `theta_sprint_minutes` (default 60, range 30–120).

However: `theta_sprint_minutes MUST be < wind_down_minutes`. The validation at hot-reload startup should enforce this. If `theta_sprint_minutes ≥ wind_down_minutes`, reject the configuration.

### 4.2 Sprint Should NOT Forcibly Close The Perp Hedge

Above I said "lock perp hedge ON." I want to refine this: don't force the perp hedge to stay open if the user has explicitly disabled it permanently. The lock-on should only apply if `perp_hedge_enabled` was `True` when the sprint started. If it was always off, don't override that.

### 4.3 Gamma-Spot Distance Calculation

The gamma-priority closing needs to know spot distance. Use the existing BTC spot price (already fetched every heartbeat) to compute `|strike - spot| / spot` as the proximity percentage. Positions with proximity < 1% are "gamma priority" and close first.

### 4.4 Sprint Status Should Emit Distinct WebSocket Event

Add `mmm_theta_sprint` event (or extend `mmm_heartbeat` with `theta_sprint_active: bool` and `sprint_minutes_remaining: int`). The UI can show a "⚡ Final Sprint" badge alongside the "🌙 Wind-Down" badge.

### 4.5 The "Both-Sides-Up" During Sprint

If both sides simultaneously hit triggers during the sprint window — the current `BOTH_SIDES_UP` state would pause the algo and wait for human input. During Theta Sprint, this is the WRONG response. 

In sprint mode, `BOTH_SIDES_UP` should automatically choose the safer action rather than waiting. The suggested default auto-action: `RESUME` (continue monitoring without new sells). Since we're already in sell-blocked mode, there's nothing to "ADD" or do differently — just continue watching. The user can override this via the `both_sides_sprint_auto_action` parameter.

### 4.6 Abandon The "Turbo" Name

"Turbo" implies aggression — faster, more, bigger. This mode is actually the OPPOSITE: more disciplined, fewer actions, more conservative. It's about precision collection in a narrowing window, not acceleration of risky activity.

Better names: **Theta Sprint**, **Final Sprint Mode**, **Harvest Phase**, or **Decay Mode**. I'll refer to it as **Theta Sprint Mode** in this document.

### 4.7 Analytics Tracking

The existing analytics system (`mmm_analytics_aggregator.py`) should track sprint performance separately:
- How much P&L was realized during the sprint window vs. during normal session
- Whether gamma-priority ordering actually reduced drawdowns vs. LIFO
- Sprint sessions vs. non-sprint sessions win rate comparison

This data will tell you in 2-3 weeks if the sprint is actually improving outcomes or just adding complexity.

---

## 5. WHAT NOT TO DO — DESIGN ANTI-PATTERNS

### 5.1 DO NOT Sell New Positions During Sprint
Already stated. This is the single most dangerous "turbo" interpretation. The premium you collect in 45 minutes of decay time with no way to run more adjustment cycles is not worth the gamma tail risk.

### 5.2 DO NOT Override Regime Checks During Sprint
Some might argue "in the last hour, regime controls are too conservative." Do not bypass regime blocks during sprint. If regime shows `TREND_TIER_3` (block all sells), it means BTC is in a strong directional move — exactly the scenario that kills 0DTE short positions in the last hour.

### 5.3 DO NOT Separate Sprint From The Session State Machine
Sprint must be a phase within the existing `MMM_RUNNING` state, not a new `MMM_SPRINT` state. The session state machine (`IDLE → RUNNING → PAUSED → STOPPED`) should not be modified. Sprint is a sub-mode of RUNNING, just like wind-down is.

### 5.4 DO NOT Make Sprint Backwards-Incompatible
All existing sessions without `theta_sprint_enabled = True` must behave exactly as before. Sprint is opt-in. The parameter validation at hot-reload must reject sprint activation if `theta_sprint_minutes ≥ wind_down_minutes` (circular dependency).

### 5.5 DO NOT Hardcode The Time-Ladder Values
The time-ladder thresholds (20%, 30%, 40%, 60%, 80% of entry premium at various minute marks) should be configurable as a single parameter: `theta_sprint_aggressiveness` with presets `CONSERVATIVE / BALANCED / AGGRESSIVE`. This maps to predefined ladder arrays. Letting users edit raw ladder arrays is too complex for a settings dialog.

---

## 6. IMPLEMENTATION PLAN (IF APPROVED)

> **Important:** No code should be written until this design is reviewed and confirmed. The following is a module-level plan.

### Phase 1 — Backend (mmm_wind_down.py + mmm_monitor.py)

**Step 1: Add Theta Sprint detection to `mmm_wind_down.py`**
- Add `is_theta_sprint_active(session, minutes_to_expiry)` function (analogous to `is_wind_down_active`)
- Sprint activates when `minutes_to_expiry <= theta_sprint_minutes AND wind_down_already_active`
- Returns `False` if sprint is not enabled or if `theta_sprint_minutes` not set

**Step 2: Add Time-Ladder Threshold Calculator**
- Add `get_sprint_close_threshold(entry_premium, minutes_to_expiry, aggressiveness)` function in `mmm_wind_down.py`
- Implements the time-ladder escalation logic (§3.2 Feature 1)
- Returns the applicable close premium threshold for a given position

**Step 3: Add Gamma-Priority Position Sorter**
- Add `get_gamma_priority_close_fills(session, side, spot_price)` function in `mmm_wind_down.py`
- Computes `spot_distance = |strike - spot| / spot` for each position
- Sorts positions: ATM-first (closest to spot), then by descending premium (highest value first)
- Replaces LIFO ordering when sprint is active

**Step 4: Modify `mmm_monitor.py` Heartbeat**
- After the existing wind-down check, add sprint check
- If sprint active: set local `SELL_BLOCKED = True` (overrides any adjustment decision)
- If sprint active: use `get_sprint_close_threshold()` instead of wind-down threshold
- If sprint active: use `get_gamma_priority_close_fills()` instead of LIFO
- If sprint active AND perp hedge was enabled at session start: force `perp_hedge_enabled = True` for this beat
- If sprint active: override heartbeat interval to `SPRINT_INTERVAL = 30` seconds
- If sprint active AND both-sides-up fires: auto-apply `both_sides_sprint_auto_action`

**Step 5: Add New Parameters to `mmm_config.py`**
```
theta_sprint_enabled         bool    default: False       hot_reload: Yes
theta_sprint_minutes         int     default: 60          hot_reload: Yes  range: 30-120
theta_sprint_aggressiveness  str     default: BALANCED    hot_reload: Yes  choices: CONSERVATIVE/BALANCED/AGGRESSIVE
both_sides_sprint_auto_action str    default: RESUME      hot_reload: Yes  choices: RESUME/STOP/ALERT
```
Validation: `theta_sprint_minutes < wind_down_minutes` (enforced in `mmm_config.py` param interdependency check)

**Step 6: Add to `mmm_state.py`**
- Add session flag `_theta_sprint_triggered: bool = False` (set once, persists session)
- Add `sprint_closes_count: int = 0` (for analytics)
- Add `sprint_pnl_realized: float = 0.0` (sprint-specific realized P&L)

**Step 7: Extend `mmm_websocket.py`**
- Extend `mmm_heartbeat` event payload: add `theta_sprint_active: bool`, `sprint_minutes_remaining: int | None`
- Add `mmm_theta_sprint` event emitted when sprint activates/deactivates (status change)

**Step 8: Extend `mmm_walkthrough.py`**
- Add sprint section to heartbeat walkthrough output: `── Theta Sprint (§X) ──`
- Shows: sprint active/inactive, time-ladder threshold in effect, gamma-priority order, SELL_BLOCKED status

### Phase 2 — Frontend

**Step 1: `MMMStatusBanner.js`**
- Add `⚡ Theta Sprint` badge (distinct color from wind-down badge — use amber/gold)
- Show `sprint_minutes_remaining` countdown in badge

**Step 2: `MMMSettingsDialog.js`**
- Add "Theta Sprint" parameter group (after Wind-Down group)
- 3 params: enabled toggle, minutes input, aggressiveness select
- Add validation warning: "theta_sprint_minutes must be less than wind_down_minutes"

**Step 3: `MMMAlgoCalculations.js`**
- Add `theta_sprint` section type to `TYPE_COLORS` map (gold/amber)
- Section-aware line coloring for `── Theta Sprint ──` section header

**Step 4: `MMMWindDownPanel` (or extend existing wind-down UI component)**
- Show both wind-down status AND sprint status in a unified "late-expiry panel"
- Display: which phase is active (Wind-Down / Theta Sprint / Both), current close threshold for each position, estimated remaining premium

### Phase 3 — Tests

New unit test file: `test_mmm_theta_sprint.py`
- Test sprint activation logic (correct timing relative to expiry)
- Test time-ladder threshold at each 15-min mark
- Test gamma-priority ordering (verifies ATM positions sort before OTM)
- Test SELL_BLOCKED flag during sprint
- Test sprint does NOT activate when `theta_sprint_enabled = False`
- Test validation that `theta_sprint_minutes < wind_down_minutes`

### Phase 4 — Analytics Integration

- Add sprint-specific fields to `mmm_analytics_storage.py`: `sprint_enabled`, `sprint_realized_pnl`, `sprint_closes_count`
- Update `mmm_analytics_aggregator.py` to compare sprint vs. non-sprint session outcomes
- Add sprint performance cards to `MMMAnalyticsSummary.js`

---

## 7. RISKS AND MITIGATIONS

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 30-sec interval overloads exchange API | Medium | Rate-limit sprint API calls; use cached premiums for non-closing calculations |
| Gamma-priority ordering misjudges "safe" OTM positions | Medium | Any position within 1.5% of spot is priority regardless of order type |
| Sprint threshold ladder closes positions too early (leaves money) | Low | `CONSERVATIVE` aggressiveness preset has wider thresholds; user controls |
| Sprint threshold ladder doesn't close fast enough (position goes deep ITM) | Medium | Perp hedge covers delta; near-expiry safety (stop_adjustment_mins, auto_close_mins) is the backstop |
| Both-sides-up auto-action wrong choice | Low | Default is RESUME (safest); user can configure; manual override always available |
| Perp hedge force-lock fails if API down | Low | Circuit breaker handles API failures; sprint doesn't REQUIRE perp hedge trades — it just tries to ensure they can happen |

---

## 8. SUMMARY & RECOMMENDATION

**Is the idea worth building?** Yes, with the specific design above.

**Is it a "turbo mode"?** No. Rename it. "Turbo" implies risk. This mode is disciplined risk-reduction-with-theta-optimization. Call it **Theta Sprint Mode**.

**What makes it genuinely new vs. what already exists:**
- Time-ladder close thresholds (not in wind-down)
- Gamma-priority position ordering (not anywhere in current system)
- Hard SELL_BLOCKED guarantee with perp hedge lock (gap in current design)
- 30-second sprint interval (below current 60s minimum)
- Both-sides-up auto-action during sprint (currently would pause waiting for human)

**What you should NOT add:**
- No new sells during sprint (ever)
- No bypass of regime checks
- No new state machine states
- No hardcoded time-ladder values (make them configurable via aggressiveness preset)

**Impact on existing MMM:**
- Zero when `theta_sprint_enabled = False` (default)
- All changes are additive (new phase detection, new sorting function, new parameter group)
- No existing module signatures change
- No existing test should break

**Sequencing recommendation:**
Build wind-down mode analytics first (to understand current late-expiry performance) before building the sprint. This gives you a baseline. If wind-down at 120 min is already capturing 85% of theta efficiently, the sprint may only marginally improve outcomes and adds operational complexity.

---

*This document represents an honest, critical analysis of the Theta Sprint Mode idea. The design is intended to be net-positive for the strategy if built carefully, but should not be rushed or confused with simple "sell more" turbo trading.*
