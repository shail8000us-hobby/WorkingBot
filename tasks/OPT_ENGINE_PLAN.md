# OPT Engine — Options Strategy Platform
## Master Plan: SSDH First, Then All Strategies via Presets

**Created:** March 18, 2026
**Status:** Planning — No code written yet
**Author context:** This plan was built from a deep analysis conversation. Every decision below has a reason rooted in that analysis. Do not skip sections.

---

## 0. How We Got Here — The Conversation Summary

This plan exists because of a specific chain of reasoning. Understanding WHY each decision was made prevents backtracking later.

### 0.1 The Original Request
The goal was to add a "Short Straddle – Short Window" preset to MMM. The analysis revealed this was feasible as a preset (ATM premium targeting + tight params), but two critical infrastructure incompatibilities were discovered:

**Problem 1 — ATM Shield is incompatible with straddle:**
The ATM Shield fires when spot comes within `atm_shield_proximity_pct` (0.5%) of the active strike. In a short strangle, the strike is OTM — so shield fires when spot moves TOWARD the strike from far away. In a short straddle, the position IS already ATM at entry. Spot is already at the strike on heartbeat 1. The shield would fire immediately, close the just-opened ATM position, and re-establish OTM — automatically converting the straddle into a strangle. It would exhaust `atm_shield_max_per_session` (default 3) within the first few minutes.

**Verdict:** `atm_shield_enabled` must be `False` for any straddle preset. ATM Shield is strangle-defense infrastructure.

**Problem 2 — wind_down_on_atm is incompatible with straddle:**
`wind_down_on_atm` triggers wind-down when any original strike becomes ATM (spot within 0.5% of entry strike). For a straddle, both original strikes ARE ATM at entry. This would trigger wind-down on heartbeat 1.

**Verdict:** `wind_down_on_atm` must be `False` for any straddle preset.

**Implication:** Without ATM Shield and without wind_down_on_atm, a pure short straddle in MMM has NO proactive retreat mechanism. Only hard stops (max_loss, max_adjustments, lot_velocity) provide protection. This makes a naked short straddle in MMM dangerous enough to be treated as a high-risk mode.

### 0.2 The Hedge Idea
To solve the naked gamma risk of a short straddle, the user proposed a ratio hedge structure:
- Sell 1 CE ATM + 1 PE ATM (combined ~$2,000 premium)
- Buy 2 CE OTM + 2 PE OTM (target ~$250 each = $1,000 total cost)
- Net credit: ~$1,000

This is the **SSDH (Short Straddle Double Hedge)** strategy.

The "double" (2×) quantity on the long side is not arbitrary — it creates a convex payoff at extreme moves:
- Spot stays near ATM: all positions decay, keep net credit (~$1,000)
- Spot moves far in either direction: the 2× long legs gain FASTER than the 1× short leg loses, eventually turning net P&L positive at extreme moves
- Max loss occurs at the long strike (the "peak loss zone"), not at infinity

This transforms an unlimited-risk short straddle into a defined-risk structure with a favorable payoff shape.

### 0.3 Why MMM Cannot Handle SSDH
MMM's entire architecture assumes the portfolio is SHORT options only:
- `calculate_standard_loss()` — only computes loss from short positions
- Trigger snapshots — monitor premium rising as signal to SELL MORE (only relevant for shorts)
- M1/M2/M3 lifecycle — harvest/recycle/rebalance frozen SHORT positions
- Strike shift — shifts SHORT positions to a new strike when premium decays
- Close-at-5 — for a long position, low premium means the position is nearly worthless (a LOSS, not a profit) — the logic is inverted
- ATM Shield — short position defense mechanism only

Adding long positions to MMM would require changing `calculate_standard_loss()`, the close-at-5 logic, all lifecycle mechanisms (M1/M2/M3), and the trigger system. This is not an additive change — it touches the core calculation engine.

### 0.4 The Architecture Decision
**MMM handles: short strangle, short straddle (pure sell) → leaves unchanged forever.**
**New OPT engine handles: all strategies requiring both buying and selling.**

The first strategy on the new engine: **SSDH**.
Once SSDH validates the engine, each additional strategy = a new preset. No engine changes needed.

This is the exact pattern MMM uses for 0DTE/SHORT_WINDOW/5DTE — same engine, different parameters.

---

## 1. Strategy Definitions

### 1.1 What Stays in MMM (Do Not Touch)

| Strategy | Legs | Engine |
|---|---|---|
| Short Strangle | Sell OTM CE + Sell OTM PE | MMM (existing, unchanged) |
| Short Straddle (pure) | Sell ATM CE + Sell ATM PE | MMM (new preset, atm_shield=False, wind_down_on_atm=False) |

### 1.2 What Goes in the New OPT Engine

| Strategy | Legs | Status |
|---|---|---|
| **SSDH** | Short 1 ATM CE + Short 1 ATM PE + Long 2 OTM CE + Long 2 OTM PE | **Phase 1 — Build this first** |
| Iron Condor | Short OTM CE + Short OTM PE + Long further OTM CE + Long further OTM PE | Phase 2 — Preset |
| Bull/Bear Spread | Long ITM + Short OTM (one direction) | Phase 3 — Preset |
| Ratio Spread | Short 1 ATM + Long 2 OTM (single direction) | Phase 3 — Preset |
| Calendar Spread | Short near expiry + Long far expiry (same strike) | Phase 4 — Requires multi-expiry handling |

---

## 2. SSDH Strategy — Complete Specification

### 2.1 Structure

```
Position    Direction   Strike          Lots    Premium (example)
─────────────────────────────────────────────────────────────────
CE Short    SELL        ATM ($100,000)  1       ~$1,000
PE Short    SELL        ATM ($100,000)  1       ~$1,000
CE Long     BUY         OTM ($104,000)  2       ~$250 each
PE Long     BUY         OTM ($96,000)   2       ~$250 each
─────────────────────────────────────────────────────────────────
Net Credit collected:  $2,000 - $500 (CE hedge) - $500 (PE hedge) = $1,000
```

Parameters:
- `initial_lots`: 1 (the short side lot count — long side = initial_lots × hedge_ratio)
- `desired_ce_premium`: ~$1,000 (ATM CE target)
- `desired_pe_premium`: ~$1,000 (ATM PE target)
- `long_hedge_premium_target`: ~$250 (OTM hedge option target)
- `long_hedge_lots_ratio`: 2.0 (long lots = initial_lots × 2)

### 2.2 Payoff Analysis

At expiry (ignoring premium for clarity):

| Spot at Expiry | Short CE P&L | Short PE P&L | Long 2× CE P&L | Long 2× PE P&L | Net |
|---|---|---|---|---|---|
| $100,000 (ATM) | +$1,000 | +$1,000 | -$500 | -$500 | **+$1,000** |
| $104,000 (long strike) | -$3,000 | +$1,000 | -$500 | -$500 | **-$3,000** |
| $108,000 | -$7,000 | +$1,000 | +$7,500 | -$500 | **+$1,000** |
| $112,000 | -$11,000 | +$1,000 | +$15,500 | -$500 | **+$5,000** |

Key insight: max loss occurs AT the long hedge strike ($104,000), not at infinity. Beyond the long strike, the 2× quantity accelerates and the position turns profitable. The structure is self-healing at extreme moves.

> [!CAUTION]
> **"Defined risk" is only true at expiry — not intraday (CRITICAL-4)**
>
> The max loss figures above are **expiry-only** numbers. During the session (with hours remaining), mark-to-market P&L can be **1.5–2× worse** than the theoretical max due to:
> - Short ATM options have the highest vega — IV spikes amplify losses disproportionately
> - Long OTM options have lower vega — they don't gain as fast as the shorts lose
> - Time value on the shorts hasn't fully decayed yet
>
> **Example:** BTC at $104K with 3 hours to expiry + a 15% IV spike:
> - Short CE mark-to-market loss: ~$4,200 (intrinsic $4K + remaining extrinsic)
> - Long CE mark-to-market gain: ~$1,800 (2× lots, but entry premium paid reduces gain)
> - Net CE loss: ~$2,800... and `max_loss_amount = $3,000` is about to fire
>
> **Consequence:** `max_loss_amount` must be set at **1.5× to 2× the theoretical structure max loss** to avoid premature stop-outs on intraday swings that would recover. The preset uses `intraday_max_loss_multiplier` (default 1.75) for this calibration.

**Breakeven calculation (upside):**
Loss from short ATM CE = 1 × (spot - ATM_strike)
Gain from long 2× OTM CE = 2 × (spot - OTM_strike)
Breakeven: spot - ATM = 2 × (spot - OTM)
→ spot = 2 × OTM - ATM
→ With ATM=$100K, OTM=$104K: Breakeven = $108,000

Max loss = (OTM_strike - ATM_strike) × short_lots × LOT_SIZE - net_credit
= $4,000 × 1 × 0.001 - $1 = ~$3 per position (example scaling)

### 2.3 What Protections Are NOT Available for SSDH

| Protection | Available? | Why Not |
|---|---|---|
| ATM Shield | ❌ NO | Already ATM at entry — fires on heartbeat 1, converts to strangle |
| wind_down_on_atm | ❌ NO | Both strikes already ATM at entry — fires on heartbeat 1 |
| MMM adjustment engine | ❌ NOT APPLICABLE | SSDH is defined-risk — adding more short lots destroys the structure |
| M1 profit harvesting | ❌ NOT APPLICABLE | No frozen short positions to harvest |
| M2 recycling | ❌ NOT APPLICABLE | No position cap relief needed — fixed structure |

### 2.4 What Protections ARE Available for SSDH

| Protection | How It Works in SSDH |
|---|---|
| Max loss amount | Hard stop — if net P&L < -(theoretical_max × `intraday_max_loss_multiplier`), close **all 4 legs** immediately |
| Session time window | Close **all** positions at end of session_window_hours regardless of P&L |
| Trailing profit stop | Protect peak net P&L — close **all** if drawdown from peak exceeds threshold |
| Structural integrity check | Every heartbeat — verify all 4 legs are present and active. If any leg missing → **emergency exit all** |
| Vega spike exit | If avg ATM premium inflates >50% without proportional price movement → alert / exit |
| Margin guardian | Same as MMM — blocks action if margin utilization too high. **Cross-engine aware** (includes MMM positions) |
| Circuit breaker | Same as MMM — isolates API failures |
| Kill switch | Emergency flatten-all endpoint — close ALL OPT positions at market, one click |

> [!WARNING]
> **Individual long leg profit/loss exits are DISABLED in Phase 1 (CRITICAL-2)**
>
> Closing a single long hedge leg (e.g., because it gained 80%) destroys the structure:
> - If the CE hedge is sold → you hold a **naked short ATM call** (unlimited upside risk)
> - If the PE hedge is sold → you hold a **naked short ATM put** (unlimited downside risk)
>
> The 4-leg structure must be treated as **atomic** — all legs live and die together.
> Individual leg management is deferred to Phase 2, after a **Structural Integrity Monitor** is built and battle-tested.

---

## 3. Architecture — Two Engines, One Platform

```
WorkingBot Options Platform
│
├── MMM Engine (webui/backend/routes/mmm/)          ← FROZEN, never modified again
│   ├── Short Strangle (existing preset)
│   ├── Short Straddle pure (new preset — atm_shield=False, wind_down_on_atm=False)
│   └── All short-sell-only strategies
│
└── OPT Engine (webui/backend/routes/opt/)           ← NEW — build this
    ├── SSDH preset (Phase 1)
    ├── Iron Condor preset (Phase 2)
    ├── Bull/Bear Spread preset (Phase 3)
    ├── Ratio Spread preset (Phase 3)
    └── Calendar Spread preset (Phase 4)
```

The two engines:
- Run as independent Flask blueprints (`/api/mmm/...` vs `/api/opt/...`)
- Have separate session states, separate activity logs, separate WebSocket namespaces
- Share only: margin guardian reporting, Telegram alerts, Delta Exchange REST client

---

## 4. What OPT Inherits From MMM (Patterns Only — Not Code)

These are the patterns to replicate, not copy-paste:

| Pattern | What to Replicate |
|---|---|
| Session lifecycle | IDLE → INITIALIZING → RUNNING → WIND_DOWN → CLOSED state machine |
| State persistence | JSON-based session state, restart recovery, reconciliation on boot |
| Activity log | Write-once audit trail, atomic write (tmp → fsync → rename), same ACTIVITY_TYPES pattern |
| WebSocket events | `emit_state_update()` every heartbeat, specific events on trade/close/error |
| Heartbeat orchestrator | `_run_heartbeat()` → schedule → execute → emit → sleep pattern |
| Parameter/preset system | DEFAULT_PARAMS dict, PARAM_RULES validation, HOT_RELOAD_PARAMS list, preset dict registry |
| Circuit breaker | 3-state (CLOSED/OPEN/HALF_OPEN), same failure threshold logic |
| Margin guardian integration | Call `_check_margin()` before any order placement |
| Unified position ledger | `positions[]` as authoritative source, `recompute_legs()` rebuilds computed views |
| Decimal arithmetic | `_D(x)` helper for all P&L accumulation |
| Eventlet-safe threading | `eventlet.patcher.original('threading').Thread` for heartbeat loop — **MANDATORY** (R2-1). Without this, `asyncio.new_event_loop()` crashes inside eventlet greenlets. Cooperative polling with `eventlet.sleep(0.01)` for any `future.result()` calls. See `mmm_monitor.py start()` for exact pattern. |
| In-flight close guard | `_being_closed` + `_being_closed_at` flag pattern on every position before async close. Auto-clear after 180s TTL. See `mmm_close_at_5.py` and `mmm_exit_all.py`. |

## 5. What OPT Builds Fresh (No Short-Specific Logic Copied)

These must be built new — not adapted from MMM:

| Component | Why Fresh |
|---|---|
| `opt_engine.py` trading core | Bidirectional P&L formula (long P&L sign is opposite of short). MMM's `calculate_standard_loss()` is short-only. |
| Position model direction field | `direction: 'long' \| 'short'` — MMM has no such concept |
| `buy_option()` execution | MMM only has `execute_entry()` (sell). Buying is new. |
| Exit logic | SSDH exits by time window + max_loss + leg-specific triggers. MMM exits by individual premium decay (close-at-5). Different concept entirely. |
| Heartbeat trigger logic | SSDH monitors NET P&L across all 4 legs. MMM monitors individual premium vs snapshot on a per-side basis. |
| Long leg lifecycle | Profit-take, loss-cut, time-close. Has no equivalent in MMM. |

---

## 6. OPT Engine — Core Design

### 6.1 Position Model

Every position in OPT has:

```python
{
    'id':            str,           # unique — e.g. 'ce_short_001', 'ce_long_001'
    'side':          'CE' | 'PE',
    'direction':     'short' | 'long',
    'type':          'core' | 'hedge',  # core = straddle legs, hedge = OTM bought legs
    'strike':        float,
    'lots':          int,
    'entry_premium': float,
    'current_premium': float,
    'unrealized_pnl': float,        # computed each heartbeat
    'status':        'active' | 'closed',
    'created_at':    str,           # ISO UTC
    'closed_at':     str | None,
    'realized_pnl':  float | None,
    'close_reason':  str | None,    # 'time_exit' | 'max_loss' | 'profit_take' | 'loss_cut' | 'manual'
}
```

**P&L formula per position:**
```
short position: unrealized_pnl = (entry_premium - current_premium) × lots × LOT_SIZE
                (positive when premium decays — the desired outcome)

long position:  unrealized_pnl = (current_premium - entry_premium) × lots × LOT_SIZE
                (positive when premium rises — the desired outcome)
```

**Net session P&L:**
```
net_pnl = sum(unrealized_pnl for all active positions) + realized_pnl_total
```

This single formula handles any combination of long and short legs. The direction field makes the sign correct automatically.

### 6.2 Heartbeat Loop (Upgraded — Structure-Aware)

MMM heartbeat has 12 steps including aggressor detection, strike shift, M1/M2/M3. OPT Phase 1 heartbeat is structurally simpler but adds **structural integrity**, **approximate Greeks**, and **adaptive acceleration**:

> [!IMPORTANT]
> **Default heartbeat interval: 30 seconds (not 120s)**
>
> An ATM straddle has **peak gamma** — the position's delta changes fastest near the money. At 100 lots, a 2% BTC move (~$2,000) in 30 seconds swings ATM premium by $800-1,200. A 120s heartbeat means **4× this swing before detection**. The 30s default is mandatory for ATM structures. (HIGH-1)

```
Step 1:  Fetch current premium for every active leg
         (4-layer fallback: WS mid → REST mark → cache → last-good)
         CRITICAL (R2-9): Failed fetches MUST return None, never 0.
         0 is a valid price for nearly worthless options. Returning 0
         makes a short position appear fully decayed (phantom profit)
         or a long position appear worthless (phantom loss). P&L engine
         skips positions with None premium and logs a fetch error.
Step 2:  Update current_premium on each position object
Step 3:  Recompute net P&L (Decimal arithmetic, bidirectional formula)
Step 4:  STRUCTURE INTEGRITY CHECK (MISSING-2):
         - Are all 4 leg types present and active?
         - If any leg missing → EMERGENCY EXIT ALL (structure broken)
         - If short exists without corresponding hedge → NAKED EXPOSURE alert
Step 5:  Approximate Greeks from premium changes (HIGH-3):
         - Track delta drift (net delta should be ~0 for straddle)
         - Track vega exposure (premium change without price change = IV shift)
         - If net delta exceeds ±0.5 → warn operator (directional tilt)
Step 6:  Safety checks:
         a) Margin check (EXCHANGE-level, cross-engine — includes MMM positions)
         b) Circuit breaker
         c) Max loss hard stop (theoretical × intraday_max_loss_multiplier)
Step 7:  Exit condition checks:
         a) Time window elapsed → WIND_DOWN → close ALL legs
         b) Net P&L < -intraday_max_loss → emergency close ALL legs
         c) Trailing profit stop → close ALL legs
         d) Vega spike exit (MISSING-5): avg premium inflation > vega_exit_multiplier
            without proportional price move → alert (auto-exit optional)
Step 8:  Adaptive interval adjustment (HIGH-1):
         - P&L < 25% of max_loss → stay at 30s
         - P&L at 25-50% of max_loss → accelerate to 15s
         - P&L > 50% of max_loss → accelerate to 10s (adaptive_min_interval)
Step 9:  Emit state update via WebSocket
Step 10: Persist session to storage
Step 11: Log heartbeat to activity log
```

No aggressor detection. No strike shifting. No M1/M2/M3. This is intentional — the strategy's risk management comes from the structure itself (the double hedge), not from the engine's reactive adjustment logic.

> [!WARNING]
> **No individual leg exits in Phase 1 (CRITICAL-2)**
>
> Steps 5d/5e from the original plan (`long_profit_close_pct`, `long_loss_cutoff_pct`) are **removed**. Closing a single hedge leg converts the structure to a naked short — see §2.4 for full explanation.

### 6.3 Entry Sequence

> [!CAUTION]
> **Atomic-or-nothing entry (CRITICAL-1, CRITICAL-3)**
>
> All 4 legs must be placed in **parallel** and fill within a unified timeout. Sequential placement creates a **naked exposure window** — if the short legs fill but hedge legs don't, you have unlimited risk. The entry is all-or-nothing: if ANY leg fails, ALL filled legs are immediately closed.

```
1.  User selects SSDH preset → parameters auto-fill
2.  User inputs: initial_lots, desired premiums, expiry, session_window_hours
3.  Engine scans chain for all 4 strikes (ATM CE, ATM PE, OTM CE, OTM PE)
4.  LIQUIDITY CHECK: For each OTM strike:
      - Verify bid-ask spread < min_otm_spread_pct (20%)
      - Verify ask depth ≥ required lots × 2
      - If either fails → REJECT with reason shown to user
5.  FEE ESTIMATE: Calculate 8-fill fee cost (4 entry + 4 exit), subtract from net credit
6.  PREVIEW shown to user:
      - All 4 strikes with live bid/ask/mid
      - Net credit (after estimated fees)
      - Theoretical max loss (at expiry)
      - Intraday max loss estimate (theoretical × intraday_max_loss_multiplier)
      - Breakeven points + required BTC move
      - Spread quality warning if any spread > 10%
7.  CROSS-ENGINE CHECK: Query MMM for active sessions on same expiry
      - If conflict → WARN user, require explicit override
8.  MARGIN CHECK: Query exchange-level margin (includes all positions from ALL engines)
      - If margin + estimated new margin > safety threshold → REJECT
9.  User confirms
10. ATOMIC ENTRY:
      a) Set entry_state = ENTRY_PLACING, persist to disk
      b) Place all 4 orders in parallel (asyncio.gather):
         - sell_option(CE, ATM_strike, initial_lots)
         - sell_option(PE, ATM_strike, initial_lots)
         - buy_option(CE, OTM_strike, initial_lots × hedge_ratio)
         - buy_option(PE, OTM_strike, initial_lots × hedge_ratio)
      c) Wait for ALL fills within entry_timeout_seconds (180s)
      d) After each fill: persist checkpoint (which legs filled)
      e) If ALL fill → set entry_state = ENTRY_COMPLETE
      f) If ANY fails → ROLLBACK:
         - Cancel unfilled orders
         - Close filled positions at market
         - Set entry_state = ENTRY_ABORTED
         - Log full detail to activity log
         - Return error to user
11. Register all 4 positions in ledger with:
      - order_id, client_order_id (opt_{session8}_{side1}_{ts8})
      - fill_confirmed_at
      - direction ('short' | 'long')
      - type ('core' | 'hedge')
12. Start heartbeat timer (30s default)
13. Emit session_started event
```

**Entry State Machine (crash recovery — CRITICAL-3):**
```
ENTRY_IDLE → ENTRY_PLACING → ENTRY_PARTIAL_FILL → ENTRY_COMPLETE → ENTRY_ABORTED
```
Each state transition is written to disk before proceeding. On restart: read last checkpoint, execute recovery:
- `ENTRY_PLACING` with no fills → clean state, retry from scratch
- `ENTRY_PARTIAL_FILL` → read which legs filled → either place remaining longs at current market or close filled shorts and abort
- `ENTRY_COMPLETE` → resume normal heartbeat
- `ENTRY_ABORTED` → no action, session is dead

### 6.4 Exit Sequence

Exit can be triggered by: time window, max loss, manual stop, trailing profit stop, structure integrity failure, vega spike.

> [!IMPORTANT]
> **Exit uses aggressive limit orders, not pure market orders (HIGH-4)**
>
> During fast moves, ATM option spreads widen to 10-30%. Pure market orders buy at the ask (worst price). Using aggressive limit orders (ask + 5% buffer) with escalation to market after 60s reduces slippage by $200-500 per leg at scale.

```
1.  Set status = WIND_DOWN
2.  MARK POSITIONS (R2-2): Before placing any close orders:
      a) Set `_being_closed = True` + `_being_closed_at = monotonic()` on each
         position about to be closed. Heartbeat exit checks skip flagged positions.
      b) Auto-clear after 180s TTL if flag is stale (crash recovery).
      c) Clear flag on successful close OR on failure/exception.
      d) On session entering WIND_DOWN, force-clear all stale _being_closed flags
         (same pattern as MMM's `_force_clear_being_closed()` in exit_all).
3.  Close SHORT legs first (highest gamma priority):
      a) Place aggressive limit orders (ask + 5% buffer) for both short legs
      b) Wait for fills, retry with wider price if needed
      c) After 60s without fill → escalate to MARKET order
      d) MUST verify fill via get_order() before proceeding
4.  PARTIAL EXIT CHECK (R2-7): If one short leg closed but the other failed:
      a) The remaining short IS still hedged by its 2× long side — not naked
      b) Escalate the failed short's close to MARKET immediately (don't wait 60s)
      c) If MARKET order also fails → KILL SWITCH (flatten everything at any price)
      d) NEVER proceed to closing longs while ANY short leg is still open
5.  Close LONG legs:
      a) Place limit orders at bid - 3% for both long legs
      b) Wait for fills
      c) After 60s → MARKET order
      d) Verify fills
6.  EXCHANGE VERIFICATION (Scenario E fix):
      a) Query exchange REST positions for all 4 strikes
      b) Confirm 0 exposure at each strike
      c) If any position still open → retry close at market
      d) NEVER transition to CLOSED until exchange confirms flat
7.  Compute session P&L:
      realized_pnl = sum(all position realized P&L)
      total_fees = sum(all fill fees)
      net_pnl = realized_pnl - total_fees
8.  REFRESH UNREALIZED P&L (R2-6): Recompute unrealized_pnl from remaining
      open positions (should be 0 after all legs closed). Treat realized_pnl +
      unrealized_pnl as an ATOMIC PAIR — never save/emit one without refreshing
      the other. This prevents stale P&L display between exit fills and next
      heartbeat. Any WS event that includes P&L must use live-computed values.
9.  Set status = CLOSED
10. Write final session summary to activity log
11. Emit session_closed event
```

**Why short legs first:** Short ATM options have the highest gamma. Every second they're open during a move is increasing risk. Long OTM options have lower gamma and lower urgency. Close the dangerous legs first, then recover value from the hedge.

> [!CAUTION]
> **A short ATM position left open overnight is catastrophic (Scenario E)**
>
> If any short leg fails to close after max retries → escalate to MARKET order with no price limit. Verify with exchange REST API that position is actually closed. Mirror MMM's `_verify_exchange_cleared()` pattern.

---

## 7. Parameters — SSDH Preset

### 7.1 Parameter Groups

**Group 1 — Entry (fixed at session creation, not hot-reloadable)**
| Parameter | Purpose | Why This Group |
|---|---|---|
| `initial_lots` | Short straddle size (long = initial_lots × hedge_ratio) | Determines net credit and max loss — can't change mid-session |
| `desired_ce_premium` | Target ATM CE premium for strike selection | Entry-time only |
| `desired_pe_premium` | Target ATM PE premium for strike selection | Entry-time only |
| `long_hedge_premium_target` | Target OTM hedge premium | Entry-time only |
| `long_hedge_lots_ratio` | Long lots = initial_lots × this value | Structural ratio — locked at entry |
| `expiry` | Option expiry datetime | Entry-time only |
| `session_window_hours` | How long the session runs (3–5 hours typical) | Operational window |

**Group 2 — Exit Triggers (hot-reloadable)**
| Parameter | Purpose |
|---|---|
| `max_loss_amount` | Hard stop — close all if net P&L drops below `theoretical_max × intraday_max_loss_multiplier` |
| `trailing_stop_pct` | Protect peak net P&L — close if drawdown from peak exceeds this % |
| `wind_down_mins_before_end` | Start wind-down this many minutes before session_window_hours elapses |

> [!WARNING]
> `long_profit_close_pct` and `long_loss_cutoff_pct` are **removed in Phase 1** (CRITICAL-2). Individual leg exits destroy the hedge structure.

**Group 3 — Safety (hot-reloadable)**
| Parameter | Purpose |
|---|---|
| `margin_yellow_pct` | Pause new orders if margin utilization exceeds this |
| `max_retries_on_fill` | How many times to retry a fill verification before failing |
| `circuit_breaker_threshold` | Consecutive API failures before circuit opens |

**Group 4 — Disabled by design (not exposed in SSDH preset)**
| Parameter | Reason Disabled |
|---|---|
| `atm_shield_enabled` | Already at ATM — fires immediately |
| `wind_down_on_atm` | Both strikes are ATM at entry |
| `harvest_enabled` | No frozen short positions |
| `recycle_enabled` | No position cap relief mechanism |
| `adjustment_enabled` | SSDH is a static structure — no reactive lot additions |

**Group 5 — Structural Safety (not hot-reloadable)**
| Parameter | Purpose |
|---|---|
| `entry_timeout_seconds` | Max time for all 4 legs to fill — abort if exceeded (default: 180) |
| `min_otm_spread_pct` | Reject entry if OTM bid-ask spread exceeds this (default: 0.20) |
| `min_otm_depth_lots` | Reject entry if OTM book depth below this (default: 10) |
| `intraday_max_loss_multiplier` | Multiply theoretical max loss by this for hard stop (default: 1.75) |
| `vega_exit_multiplier` | Exit if avg premium inflation exceeds this without price move (default: 1.50) |
| `structure_integrity_check` | `True` — always on, cannot be disabled |

### 7.2 SSDH Preset Default Values (to be tuned with real session data)

```python
PRESET_SSDH = {
    'strategy':                    'ssdh',
    'session_window_hours':        4.0,        # 4-hour window default
    'long_hedge_lots_ratio':       2.0,        # 2× long vs 1× short
    'max_loss_amount':             3000,       # in USD (base — multiplied by intraday_max_loss_multiplier)
    'trailing_stop_pct':           0.50,       # protect 50% of peak profit
    'wind_down_mins_before_end':   30,         # start closing 30 mins before window ends
    # Heartbeat — fast by default for ATM gamma (HIGH-1)
    'adjustment_interval':         30,         # 30s default (NOT 120s — ATM has peak gamma)
    'adaptive_interval_enabled':   True,
    'adaptive_max_interval':       60,         # never slower than 60s for ATM structures
    'adaptive_min_interval':       10,         # accelerate to 10s when P&L > 50% of max_loss
    # Structural safety (Group 5)
    'entry_timeout_seconds':       180,        # all 4 legs must fill within this
    'intraday_max_loss_multiplier': 1.75,      # max_loss = theoretical_max × this
    'min_otm_spread_pct':          0.20,       # reject entry if OTM spread > 20%
    'min_otm_depth_lots':          10,         # reject entry if OTM book depth < this
    'vega_exit_multiplier':        1.50,       # exit if avg premium rises 50%+ without price move
    'structure_integrity_check':   True,       # always on — cannot be disabled
    # Disabled — structural incompatibilities
    'atm_shield_enabled':          False,
    'wind_down_on_atm':            False,
    'harvest_enabled':             False,
    'recycle_enabled':             False,
    'adjustment_enabled':          False,
    # REMOVED in Phase 1 (CRITICAL-2 — breaks hedge structure):
    # 'long_profit_close_pct':  80.0,   # DO NOT ADD — see §2.4
    # 'long_loss_cutoff_pct':   75.0,   # DO NOT ADD — see §2.4
}
```

---

## 8. File Structure

```
webui/backend/routes/opt/
├── opt_api.py              API endpoints: /api/opt/sessions, /start, /stop, /state
├── opt_monitor.py          Heartbeat orchestrator — MMMMonitor equivalent
├── opt_engine.py           Bidirectional P&L, leg management, exit logic
├── opt_executor.py         buy_option() + sell_option() + close_position()
├── opt_entry.py            Atomic entry orchestrator + crash recovery state machine (MISSING-1)
├── opt_integrity.py        Structural integrity monitor — every heartbeat (MISSING-2)
├── opt_reconciler.py       Per-strike, per-direction position reconciliation (MISSING-4)
├── opt_greeks.py           Approximate Greek computation from premium changes (HIGH-3)
├── opt_kill.py             Emergency flatten-all kill switch (MISSING-3)
├── opt_state.py            Position model, DEFAULT_PARAMS, session dataclass
├── opt_config.py           PARAM_RULES, HOT_RELOAD_PARAMS, validation
├── opt_presets.py          PRESET_SSDH + future presets (iron condor, etc.)
├── opt_activity.py         Activity types, write-once log
├── opt_websocket.py        WebSocket event emitters
└── opt_safety.py           max_loss check, cross-engine margin check, circuit breaker wrapper

webui/frontend/src/components/opt/
├── OPTDashboard.js         Main dashboard — mirrors MMMDashboard layout
├── OPTSessionCreate.js     Session creation form with preset selector + preview
├── OPTPositionsTable.js    Shows all 4 legs — short = red/orange, long = green
├── OPTSettingsDialog.js    Parameter editor for active session (hot-reload params)
├── OPTStatusBanner.js      Session status + time remaining + net P&L
├── OPTPnLPanel.js          Net P&L breakdown: short legs + long legs + total
└── optService.js           API client — mirrors mmmService.js
```

---

## 9. Implementation Phases

### Phase 1 — Foundation (State + Config + API skeleton)

**Files:** `opt_state.py`, `opt_config.py`, `opt_presets.py`, `opt_api.py` (stub endpoints)

**Work:**
- Define position model with `direction` field
- Define `DEFAULT_PARAMS` with all SSDH parameters
- Define `PARAM_RULES` with validation logic
- Define `PRESET_SSDH`
- Define session state dataclass (lifecycle: IDLE → INITIALIZING → RUNNING → WIND_DOWN → CLOSED)
- Register blueprint in `app.py` with `/api/opt/` prefix
- Stub all API endpoints (return 501 for now)
- Write sealed unit tests for position P&L formula (short and long, verify sign correctness)

**Done when:** `GET /api/opt/sessions` returns `[]` with no errors. All P&L formula tests pass.

### Phase 2 — Execution Layer

**Files:** `opt_executor.py`

**Work:**
- `buy_option(symbol, strike, lots, expiry)` → place buy order → poll for fill → return fill dict
- `sell_option(symbol, strike, lots, expiry)` → place sell order → poll for fill → return fill dict
- `close_position(position, reason)` → close via appropriate side (buy back short / sell back long)
- Fill verification with retry logic (same pattern as MMM's `execute_entry()`)
- Partial fill rejection (same robustv2 Fix #3 pattern)

**Done when:** Can place a test buy order on demo exchange and get verified fill back.

### Phase 3 — Heartbeat + P&L

**Files:** `opt_monitor.py`, `opt_engine.py`

**Work:**
- `_run_heartbeat()` loop with adaptive interval
- Fetch all 4 leg premiums per heartbeat
- `compute_net_pnl()` using bidirectional formula
- Peak P&L tracking for trailing stop
- Circuit breaker integration
- `opt_activity.py` — write heartbeat events to log

**Done when:** A live session can run, premiums update each heartbeat, net P&L computes correctly, activity log writes.

### Phase 4 — Entry + Exit Logic

**Files:** `opt_entry.py`, `opt_monitor.py`, `opt_engine.py`, `opt_api.py` (fully implemented)

**Work:**
- Chain scan for all 4 strikes (ATM CE, ATM PE, OTM CE, OTM PE)
- OTM liquidity pre-check (spread + depth validation) (HIGH-2)
- Fee estimation for 8-fill round trip (HIGH-5)
- Entry preview with full risk metrics: strikes, premiums, net credit (after fees), theoretical max loss, intraday max loss estimate, breakeven points (MISSING-7)
- Cross-engine session awareness: query MMM for conflicts on same expiry (MISSING-6)
- Exchange-level margin check before order placement (CRITICAL-5)
- Atomic parallel entry: place all 4 orders simultaneously, rollback on any failure (CRITICAL-1)
- Entry state machine with persistent checkpoints for crash recovery (CRITICAL-3)
- Exit sequence: aggressive limit orders, short legs first, exchange verification (HIGH-4)
- Exit trigger evaluation: max_loss (with intraday multiplier), trailing_stop, time window, vega spike
- `wind_down` phase: close positions in order with elevated urgency
- Manual stop + kill switch via API (MISSING-3)

**Done when:** Full SSDH session can run from start to close without manual intervention.

### Phase 5 — WebSocket + Activity

**Files:** `opt_websocket.py`, `opt_activity.py`

**Work:**
- `emit_state_update()` every heartbeat (same pattern as MMM's `mmm_state_snapshot`)
- `emit_leg_close()` on any position close
- `emit_session_closed()` on session end
- Activity log types: `session_started`, `leg_entry`, `leg_close`, `heartbeat_pnl`, `wind_down_started`, `session_closed`

**Done when:** Frontend can receive live updates.

### Phase 6 — Frontend

**Files:** All frontend files listed in §8

**Work:**
- `OPTDashboard.js` — renders all panels
- `OPTSessionCreate.js` — SSDH preset selector, parameter inputs, strike preview table, confirm button
- `OPTPositionsTable.js` — 4-leg table: SHORT CE | SHORT PE | LONG CE (×2) | LONG PE (×2), color-coded by direction
- `OPTStatusBanner.js` — session timer (countdown to window end), net P&L, status
- `OPTPnLPanel.js` — breakdown: short legs P&L | long legs P&L | net total
- `optService.js` — all API calls

**Done when:** Full session lifecycle visible and controllable from the UI.

### Phase 7 — Sealed Tests + Canary Validation

**Work:**
- Seal all core calculation functions (P&L formula, exit triggers, breakeven calculation)
- Run 3+ complete SSDH sessions on canary account
- Validate: net P&L matches exchange P&L, fills verified, no orphan positions after session close
- Document any bugs found in `tasks/lessons.md`

**Done when:** 3 canary sessions completed without manual intervention.

---

## 10. The Preset Expansion Path

Once SSDH validates the engine (Phase 7 complete), each new strategy is added as a preset — no engine changes needed.

### Iron Condor
```
Sell OTM CE + Sell OTM PE (wider strikes)
Buy further OTM CE + Buy further OTM PE (protection)
Ratio: 1:1 (not 2× — equal lots on long and short)
Key difference from SSDH: strikes are NOT ATM — OTM entry, ATM Shield CAN be used
New preset: PRESET_IRON_CONDOR with different strike_offset_pct instead of ATM scanning
```

### Bull/Bear Call Spread
```
Buy ITM CE + Sell OTM CE (bullish)
or
Buy ITM PE + Sell OTM PE (bearish)
Net debit (costs money upfront)
Engine already handles this — just reverse direction of entry order
New preset: PRESET_BULL_CALL_SPREAD with debit_mode=True
```

### Ratio Spread (single direction)
```
Sell 1 ATM CE + Buy 2 OTM CE (upside ratio)
or
Sell 1 ATM PE + Buy 2 OTM PE (downside ratio)
Half of SSDH — only one side
New preset: PRESET_RATIO_SPREAD with pe_enabled=False or ce_enabled=False
```

### Calendar Spread (Phase 4 — requires extra work)
```
Sell near-expiry option + Buy same-strike far-expiry option
Requires: multi-expiry chain scanning, separate expiry tracking per leg
This is the only strategy requiring engine changes — deferred to Phase 4
```

---

## 11. What Stays Frozen — MMM

**Zero changes to MMM.** This is a rule, not a preference.

The MMM engine is production-hardened across:
- 26 robustv2 fixes
- 3 active presets (0DTE, SHORT_WINDOW, 5DTE)
- M1/M2/M3 lifecycle system
- ATM Shield
- Perp futures delta hedge
- Split Ledger
- Breakeven Engine
- Gamma Detector
- Trade Transparency / Audit Trail
- Adaptive Tuning System

Any modification to MMM requires going through the existing plan review process and updating `tasks/lessons.md`. **SSDH and the OPT engine never require a change to MMM.**

If a new short-only strategy is needed (e.g., pure short straddle), it gets added as a preset in `mmm_dte_presets.py` with:
- `atm_shield_enabled: False`
- `wind_down_on_atm: False`
- `harvest_enabled: True` (frozen short positions still benefit from M1)
- `max_lots_per_side: 5` (tight cap — no proactive retreat, protect via hard limits)

---

## 12. Risk Rules for Using SSDH in Live Trading

These are NOT code rules — they are operational rules for the human operator.

1. **Only use SSDH when IV is moderate (not spiking).** High IV makes ATM premium expensive — you're paying a lot for the short straddle and hedging into high IV on the OTM options. Sweet spot: IV between 35–55%.

2. **Do not run SSDH on days with major macro events** (FOMC, CPI, ETF decisions). A binary event can spike BTC beyond the long hedge strikes faster than the engine can react.

3. **Session window 3–5 hours maximum.** The theta decay curve is steepest in the final hours before expiry. SSDH works best as a theta harvest in a defined window — not as a full-DTE hold.

4. **Start with initial_lots = 1.** The structure at 1 lot is well-defined. At 5 lots, you have 5 short ATM + 10 long OTM — the gamma exposure from 5 short ATM options in a volatile market is significant even with the hedge.

5. **Do not run MMM and SSDH simultaneously on the same expiry.** ~~The sessions don't know about each other's positions.~~ **This is now enforced in code** (CRITICAL-5): `opt_entry.py` queries MMM active sessions before entry and warns the operator. `opt_safety.py` queries exchange-level margin (which includes ALL positions from ALL engines) before any order placement.

6. **The max_loss_amount must reflect the STRUCTURE's max loss, not a generic dollar amount.** Max loss for 1-lot SSDH ≈ (OTM_strike - ATM_strike) × LOT_SIZE - net_credit. **Important:** The hard stop fires on mark-to-market, not expiry payoff. Intraday max loss can be **1.5–2× higher** than theoretical due to time value and vega (CRITICAL-4). The preset's `intraday_max_loss_multiplier` (default 1.75) accounts for this.

7. **Account for fees in net credit calculation (HIGH-5).** With 8 fills (4 entry + 4 exit), fees can consume 4–8% of net credit at small lot sizes. The entry preview shows net credit *after* estimated fees.

8. **Validate hedge ratio effectiveness before entry (HIGH-6).** The 2× hedge ratio's effectiveness depends on the ATM–OTM strike distance. If the breakeven point requires >8% BTC move, the hedge may not activate within the session window. The entry preview shows breakeven points and warns if they're too far.

---

## 13. Critical Implementation Notes

**Do not copy `calculate_standard_loss()` from MMM.**
It assumes all positions are short. Using it in OPT would give wrong P&L for long legs. Build `compute_net_pnl()` fresh in `opt_engine.py` using the bidirectional formula in §6.1.

**The `direction` field is the most important design decision.**
Every downstream calculation — P&L, close logic, fill verification — branches on this field. Get it right in `opt_state.py` first. Write sealed tests for the P&L formula before building anything else.

**Close sequence matters for risk.**
Short legs first, always. A remaining open short ATM option during a fast BTC move is pure gamma risk. If a close order fails on the short leg, retry aggressively. Do not proceed to closing long legs until short legs are confirmed closed. **After all legs closed: verify with exchange REST API that all positions show 0 exposure. NEVER transition to CLOSED until exchange confirms flat.**

**WebSocket namespace must be separate from MMM.**
MMM uses the default namespace (`/`). OPT should use a named namespace (`/opt`). Frontend connects to both independently.

**Activity log file must be separate from MMM's.**
MMM writes to `webui/backend/data/mmm_activity_log.json`. OPT should write to `webui/backend/data/opt_activity_log.json`. Never share a log file between engines.

**Reconciliation must be per-strike, per-direction — never net across strikes (Scenario F).**
The exchange reports NET positions. OPT's reconciliation must query per-strike, per-direction and match using `client_order_id` prefix `opt_` to distinguish OPT-owned positions from MMM or manual trades. Naive netting across strikes will produce ghost mismatches.

**Track fees in session state (HIGH-5).**
Add `total_fees` to session state. Track fees from every fill. Subtract from net credit in P&L display. Same pattern as MMM's fee tracking.

**OTM option liquidity is not guaranteed on Delta Exchange India (HIGH-2).**
OTM BTC options 4%+ away from spot often have no quotes or spreads >30%. Always run the liquidity pre-check in `opt_entry.py` before showing the entry preview. Reject entry if spread > `min_otm_spread_pct` or depth < `min_otm_depth_lots`.

**Kill switch must be independent of session state (MISSING-3).**
`/api/opt/kill` must work regardless of session status. It cancels all open orders, closes all positions at market (shorts first), verifies with exchange, and logs everything. It is the last line of defense.

**Structure integrity is non-negotiable (MISSING-2).**
Every heartbeat must verify all 4 legs are present and active. If any leg is missing (exchange auto-liquidation, manual intervention, API glitch), the structure is broken. Broken structure = immediate emergency exit of remaining legs. This cannot be disabled.

**Hedge ratio breakeven should be shown in entry preview (HIGH-6).**
If the 2× hedge ratio with the selected OTM strike produces breakeven points requiring >8% BTC move, warn the operator. At 4% OTM distance, breakeven = 8% move. At 6% OTM distance, breakeven = 12% move — unlikely to activate in a 3–5 hour session.

**OPT monitor thread MUST use real OS threads — eventlet fix (R2-1).**
The backend runs under `gunicorn worker_class=eventlet`. Eventlet monkey-patches `threading.Thread` into greenlets. `asyncio.new_event_loop()` cannot run inside a greenlet — it crashes with "Cannot run the event loop while another loop is running". Use `eventlet.patcher.original('threading').Thread` for the heartbeat loop thread — exact pattern from MMM's `mmm_monitor.py start()`. Any `future.result()` calls from greenlets must use cooperative polling (`eventlet.sleep(0.01)` loop), never blocking waits. See `lessons.md` [2026-03-10] and [2026-03-11] for the full failure chain.

**Use `paid_commission` for fee tracking, NOT `commission` — Delta Exchange API quirk (R2-3).**
`order['commission']` = string `"0"` (reserved amount, always 0 for filled orders). `order['paid_commission']` = string like `"0.04140325"` (actual USDT fee charged). Both are strings — always cast with `float()`. Use fallback chain: `float(od.get('paid_commission', 0) or od.get('commission', 0) or 0)`. Every `smart_execute` / `emergency_execute` call site MUST extract fees and add to `session['total_fees']`. Without this, fees will be invisible and P&L overstated — this exact bug persisted in MMM for weeks before discovery.

**Margin check must use `blocked_margin`, not `portfolio_margin` — Delta Exchange API (R2-4).**
`blocked_margin` = actual locked collateral = what Delta Exchange UI shows as "Blocked as Margin". `portfolio_margin` = theoretical risk model value (can exceed actual collateral, causing premature safety triggers). Priority: `blocked_margin` > `portfolio_margin` > `position_margin + order_margin`. This matches the fix in `mmm_margin_guardian.py`. See `lessons.md` [2026-03-13].

**Session stores expiry as ddmmyyyy; Delta Exchange symbols use ddmmyy suffix (R2-5).**
When building symbol strings for reconciliation or order queries, always convert using an `expiry_to_symbol_suffix()` helper (e.g., `11032026` → `110326`). Never use the raw expiry parameter directly in symbol string comparisons. This exact mismatch silently broke MMM's orphan scan for an entire session — see `lessons.md` [2026-03-11].

**Price fetch failures MUST return None, never 0 (R2-9).**
0 is a valid price (for nearly worthless options). Returning 0 on fetch failure makes the P&L engine think a short position is fully decayed (displaying phantom profits) or a long position is worthless (displaying phantom losses). In MMM, this bug inflated displayed P&L by hundreds of dollars for sessions with 76+ frozen lots. The P&L engine should skip positions with None premium and log a fetch error. See `lessons.md` [2026-03-19] — Bug A.

**`_being_closed` flag requires TTL auto-clear (R2-2).**
Always set `_being_closed_at = time.monotonic()` alongside `_being_closed = True`. Auto-clear if stuck >180 seconds (crash recovery). Clear on successful close or failure. When entering WIND_DOWN or exit_all, force-clear ALL stale flags first. Without TTL, a crash during close permanently locks positions — this bug left MMM positions exposed for 30+ minutes on March 11. See `lessons.md` [2026-03-15].

**After closing positions, refresh unrealized_pnl before saving or emitting (R2-6).**
Any code path that updates `realized_pnl` MUST also refresh `unrealized_pnl`. Treat them as an atomic pair. Without this, the WS event after a close will show `realized(new) + unrealized(stale)` — overcounted P&L. In MMM, this made displayed P&L exceed peak_pnl, which is the diagnostic signature. See `lessons.md` [2026-03-19] — Bug B.

---

## 14. Success Criteria — Phase 1 Complete

Before writing any Phase 2 code, Phase 1 is complete when:
- [ ] `GET /api/opt/sessions` returns `[]` with HTTP 200
- [ ] `GET /api/opt/presets` returns SSDH preset metadata
- [ ] All P&L formula sealed tests pass (short, long, net, edge cases)
- [ ] Blueprint registered in `app.py` without breaking any MMM endpoint
- [ ] `curl http://localhost:5555/api/health` still passes after registering OPT blueprint
- [ ] Structural integrity check runs every heartbeat and detects missing legs
- [ ] Entry state machine persists checkpoints and handles crash recovery
- [ ] Kill switch endpoint (`/api/opt/kill`) flattens all positions regardless of session state
- [ ] Cross-engine margin query includes all positions from MMM + OPT

---

## 15. Context Files To Read Before Touching Any Code

| File | What To Read |
|---|---|
| `AI_MMM_CONTEXT.md` | Full MMM algorithm — understand everything before building OPT so you don't reinvent poorly |
| `tasks/lessons.md` | All mistakes already made — do not repeat them |
| `webui/backend/routes/mmm/mmm_perp_hedge.py` | The best architectural precedent for a new instrument type alongside MMM |
| `webui/backend/routes/mmm/mmm_state.py` | Unified Position Ledger — understand the `positions[]` model before designing OPT's equivalent |
| `webui/backend/routes/mmm/mmm_executor.py` | Understand how MMM places and verifies fills before building opt_executor.py |
| `CLAUDE.md` | Project rules — port 5555, USD→INR conversion (once only), LaunchAgent restart protocol |

---

## 16. Failure Scenarios (What Goes Wrong Without Fixes)

These scenarios are not theoretical — they represent the specific failure modes that the audit fixes prevent.

### Scenario A: Hedge Leg Fails to Fill
- Sell ATM CE → fills at $1,050. Sell ATM PE → fills at $980.
- Buy OTM CE → no quotes available, 3 reprice attempts fail.
- **NOW:** Holding naked short straddle ($2,030 premium collected, unlimited risk).
- BTC moves +6% → short CE loss = ~$6,000 × lots × 0.001. No hedge.
- **Without fix:** Unlimited loss. **With atomic entry (CRITICAL-1):** Rolled back — shorts closed immediately, session aborted.

### Scenario B: IV Spike Without Price Move
- SSDH entered at IV=40%, net credit $100 (100 lots).
- Unexpected news → IV jumps to 60%.
- Short ATM premiums: $1,000 → $1,500 (+50%). Long OTM premiums: $250 → $350 (+40%).
- Net P&L change: -$100 (shorts) + $40 (longs) = **-$60 on a $100 net credit** (60% lost from vega alone).
- **Without fix:** `max_loss_amount` fires, exit at worst prices. **With vega monitor (MISSING-5):** Early detection, wait for IV reversion or controlled exit.

### Scenario C: Long Leg Profit Take → Naked Short
- BTC rallies 3%. Long OTM CE (2 lots) gains 80%.
- `long_profit_close_pct` fires → sells both long CE lots.
- **NOW:** Short 1 ATM CE (**NAKED**), Short 1 ATM PE, Long 2 OTM PE.
- BTC continues rallying 5% more. ATM CE loss: **unlimited**.
- **Without fix:** Unlimited loss. **With CRITICAL-2 fix:** Individual leg exits disabled. All-or-nothing exit only.

### Scenario D: Crash During Entry (2 of 4 Legs Filled)
- Sell ATM CE → fills. Sell ATM PE → fills. System crashes.
- After restart: 2 short positions on exchange, no hedge, session state unclear.
- **Without fix:** Orphaned naked short straddle. **With entry state machine (CRITICAL-3):** Detect checkpoint → place longs or close shorts and abort.

### Scenario E: Exit Partial — Short Leg Buyback Fails
- Time window reached → wind down. Buy back short CE → fills. Buy back short PE → API timeout, retries fail.
- **NOW:** 1 short ATM PE still open + longs still open. Not a defined-risk structure.
- **Without fix:** Short PE left open overnight = catastrophic. **With exchange verification (§6.4):** Escalate to market order, verify with exchange API before CLOSED.

### Scenario F: Reconciliation Deletes Hedge Legs
- Session running, all 4 legs active. Reconciliation queries exchange.
- Exchange shows NET position across strikes. Naive reconciliation mismatches and "corrects" by removing positions.
- **Without fix:** Phantom/orphan positions. **With per-strike reconciliation (MISSING-4):** Match by `client_order_id` prefix `opt_`, never net across strikes.

---

## 17. Production Audit Summary

**Round 1 audit:** 2026-03-21 | **Verdict:** NEEDS FIXES → **All fixes applied**
**Round 2 audit:** 2026-03-21 | **Verdict:** PLAN IS STRONG → **11 remaining gaps fixed**

### Round 1 — Critical Flaws (Fixed)

| # | Flaw | Fix Applied | Plan Section |
|---|---|---|---|
| C-1 | Sequential entry creates naked exposure | Atomic parallel entry with rollback | §6.3 |
| C-2 | Individual leg exits destroy hedge | Removed in Phase 1; atomic exit only | §2.4, §6.2, §7.2 |
| C-3 | No crash recovery for partial entry | Entry state machine with persistent checkpoints | §6.3 |
| C-4 | Intraday P&L exceeds theoretical max | `intraday_max_loss_multiplier` (1.75×) | §2.2, §7.1, §7.2 |
| C-5 | No cross-engine margin guard | Exchange-level margin query (all engines) | §6.3, §12, §13 |

### Round 1 — High-Risk Weaknesses (Fixed)

| # | Weakness | Fix Applied | Plan Section |
|---|---|---|---|
| H-1 | Heartbeat too slow (120s) for ATM gamma | Default 30s, adaptive down to 10s | §6.2, §7.2 |
| H-2 | OTM liquidity not guaranteed | Liquidity pre-check (spread + depth) | §6.3, §13 |
| H-3 | No Greek monitoring | Approximate delta/vega tracking per heartbeat | §6.2, §8 |
| H-4 | Exit slippage from market orders | Aggressive limit orders with market escalation | §6.4 |
| H-5 | No fee accounting | Fee estimation in preview + tracking in session | §6.3, §7.2, §12, §13 |
| H-6 | Hedge ratio not validated | Breakeven calculator in entry preview | §6.3, §12, §13 |

### Round 1 — Missing Features (Added)

| # | Feature | File | Plan Section |
|---|---|---|---|
| M-1 | Atomic Entry Orchestrator | `opt_entry.py` | §6.3, §8 |
| M-2 | Structural Integrity Monitor | `opt_integrity.py` | §6.2, §8 |
| M-3 | Kill Switch (flatten-all) | `opt_kill.py` | §8, §13 |
| M-4 | Position Reconciliation | `opt_reconciler.py` | §8, §13 |
| M-5 | Vega-Triggered Exit | `opt_engine.py` | §6.2 |
| M-6 | Cross-Engine Session Awareness | `opt_entry.py` | §6.3, §12 |
| M-7 | Full Risk Metrics in Entry Preview | `opt_entry.py` | §6.3 |

### Round 2 — Remaining Gaps (Fixed)

These gaps were found by cross-referencing `lessons.md` (60+ MMM production bugs) against the OPT plan. Every one of these burned MMM in production — they WILL burn OPT if not addressed.

| # | Severity | Gap | Fix Applied | Plan Section |
|---|---|---|---|---|
| R2-1 | **CRITICAL** | Eventlet greenlet/asyncio crash — OPT monitor dies on first heartbeat | Eventlet-safe threading pattern mandatory in §4, implementation note in §13 | §4, §13 |
| R2-2 | **CRITICAL** | No `_being_closed` guard — exit race causes double-close on exchange | In-flight guard with 180s TTL auto-clear added to §6.4 and §13 | §4, §6.4, §13 |
| R2-3 | **HIGH** | `paid_commission` vs `commission` — fees always 0 | Correct API field + fallback chain documented in §13 | §13 |
| R2-4 | **HIGH** | `blocked_margin` vs `portfolio_margin` — wrong utilization | Field priority documented in §13 | §13 |
| R2-5 | **HIGH** | Expiry format ddmmyyyy vs ddmmyy — reconciliation silently fails | `expiry_to_symbol_suffix()` pattern documented in §13 | §13 |
| R2-6 | **HIGH** | Stale `unrealized_pnl` after exit fills — P&L overcounted | Atomic refresh added to §6.4 Step 8, implementation note in §13 | §6.4, §13 |
| R2-7 | **MEDIUM** | No partial exit recovery — half-dismantled structure | Partial exit check with MARKET escalation added to §6.4 Step 4 | §6.4 |
| R2-8 | **MEDIUM** | No per-heartbeat close cap | Inherited from §4 guardian pattern; note added | §4 |
| R2-9 | **MEDIUM** | Cache miss returns 0 instead of None — phantom P&L | None-return mandate added to §6.2 Step 1 and §13 | §6.2, §13 |
| R2-10 | **LOW** | Phase ordering: WS needed before exit testing | Note: use stub emitters in Phase 4 until Phase 5 | §9 |
| R2-11 | **LOW** | Reconciler needs `expiry_to_symbol_suffix()` | Covered by R2-5 in §13 | §13 |

> [!TIP]
> **Recommendation:** Begin Phase 1 implementation. First 5 canary sessions at 1 lot with operator watching every heartbeat.
