# Iron Condor Algo — Complete Implementation Plan

**File:** `IC_ALGO_PLAN.md`
**Created:** 2026-03-24
**Status:** Phase 1+2+3 COMPLETE — Core backend + execution/monitor + API/WebSocket/Telegram (21 files, 49 tests pass)
**Last Updated:** 2026-03-24 (Phase 3 committed to git)
**Author:** AI + Operator
**Target exchange:** Delta Exchange India (BTC options)
**Instrument:** BTC 0DTE / weekly options, same as MMM

---

## Table of Contents

1. [Strategy Overview](#1-strategy-overview)
2. [Comparison with MMM Algo](#2-comparison-with-mmm-algo)
3. [Complete File Structure](#3-complete-file-structure)
4. [State Model](#4-state-model)
5. [Parameters](#5-parameters)
6. [Algorithm Phases — Heartbeat Design](#6-algorithm-phases--heartbeat-design)
7. [Entry Logic — Strike & Wing Selection](#7-entry-logic--strike--wing-selection)
8. [P&L Formulas](#8-pl-formulas)
9. [Adjustment Logic — The Auto-Adjustment Mind](#9-adjustment-logic--the-auto-adjustment-mind)
10. [Exit Logic & Cycle Management](#10-exit-logic--cycle-management)
11. [Safety System](#11-safety-system)
12. [API Design](#12-api-design)
13. [WebSocket Events](#13-websocket-events)
14. [WebUI Design](#14-webui-design)
15. [Testing Plan](#15-testing-plan)
16. [Implementation Phases](#16-implementation-phases)
17. [What We Reuse from MMM](#17-what-we-reuse-from-mmm)

---

## 1. Strategy Overview

### What is an Iron Condor?

An Iron Condor is a **defined-risk premium-selling strategy** combining two credit spreads:

```
 Max Profit Zone (flat top)
 ─────────────────────────────────────
         │              │
   Long  │   Short      Short   Long
   Put   │   Put         Call    Call
  (wing) │  (short)    (short)  (wing)
         │              │
  ───────┼──────────────┼────────────
  [P-W]  [P]          [C]      [C+W]
                 ^
            Market center
            at entry

P   = short put strike
P-W = long put strike (W = wing width)
C   = short call strike
C+W = long call strike
```

**4 legs:**
| Leg | Type | Action | Premium |
|-----|------|--------|---------|
| Short Put (SP) | OTM Put | Sell | +credit |
| Long Put (LP) | Further OTM Put | Buy | -debit |
| Short Call (SC) | OTM Call | Sell | +credit |
| Long Call (LC) | Further OTM Call | Buy | -debit |

**Net credit** = (SP + SC) - (LP + LC) — this is your max profit.

**Max loss** = Wing Width - Net Credit (in USD per BTC, × lots × 0.001 BTC/lot)

**Breakeven points:**
- Upper breakeven = SC + net_credit
- Lower breakeven = SP - net_credit

### Why run it continuously?

Institutions run Iron Condors in a **rolling cycle**:
1. Open a condor (collect credit)
2. Auto-adjust if market threatens a short strike
3. Close at profit target (50% of max credit) or DTE threshold
4. Immediately open next cycle
5. Repeat 24/7 (crypto never closes)

This converts the Iron Condor from a "set and forget" trade into a **continuous premium-harvesting engine** — the same philosophy as MMM.

---

## 2. Comparison with MMM Algo

| Aspect | MMM (existing) | Iron Condor (new) |
|--------|---------------|-------------------|
| Legs | 2 (CE + PE naked sells) | 4 (CE spread + PE spread) |
| Max loss | Unlimited (naked) | **Hard-defined**: `(wing_width - net_credit) × lots × 0.001` |
| Entry | Continuous selling on trigger | One-shot entry per cycle (4 orders simultaneously) |
| Adjustment | Sell more lots on triggered side | Roll one spread or entire condor |
| Lot management | Complex (adjustment_fills ledger) | Simple (fixed lots per cycle) |
| Premium source | Both short legs | Net of all 4 legs |
| P&L tracking | Per-position lot ledger | Per-leg entry price vs mark price |
| Safety | 7-layer (naked risk) | 3-layer (defined risk — simpler) |
| Wing | None | Core feature — long options cap loss |
| Cycle | Indefinite (continuous) | Discrete cycles (open → monitor → close → repeat) |
| Risk per trade | Unlimited | `(wing_width - credit) × lots × 0.001 BTC` |

**Key architectural difference:**
MMM sells continuously to "cover loss" (dynamic lot sizing). IC sells once, then *adjusts the structure* to defend it. The math is fundamentally different.

---

## 3. Complete File Structure

```
webui/backend/routes/ic/           ← new module (mirrors mmm/)
├── __init__.py
├── ic_constants.py                ← LOT_SIZE_BTC, strike_key reuse, IC-specific consts
├── ic_state.py                    ← Session state model + position ledger
├── ic_config.py                   ← Parameter definitions, validation, hot-reload list
├── ic_storage.py                  ← JSON persistence (mirrors mmm_storage.py)
├── ic_engine.py                   ← P&L math: net_credit, max_loss, unrealized_pnl
├── ic_strike_selector.py          ← Entry logic: find SP/LP/SC/LC strikes + dynamic chain fetch
├── ic_greeks.py                   ← Portfolio Greeks computation from exchange data
├── ic_executor.py                 ← Order placement (batch API + atomicity rollback)
├── ic_monitor.py                  ← Background heartbeat loop (mirrors MMMMonitor)
├── ic_trigger.py                  ← Breach detection: is short strike threatened?
├── ic_adjuster.py                 ← Adjustment decisions: roll / widen / new cycle
├── ic_roller.py                   ← Roll execution: close leg + reopen at new strike
├── ic_safety.py                   ← Safety checks: max loss, margin, DTE limits
├── ic_exit.py                     ← Exit logic: profit target, DTE close, force close
├── ic_cycle.py                    ← Cycle lifecycle: ENTRY → ACTIVE → EXIT → NEXT
├── ic_websocket.py                ← WebSocket emit helpers
├── ic_activity.py                 ← Activity log (mirrors mmm_activity.py)
├── ic_telegram.py                 ← Telegram alerts
├── ic_api.py                      ← Flask Blueprint REST endpoints
└── tests/
    ├── __init__.py
    ├── test_ic_engine.py
    ├── test_ic_strike_selector.py
    ├── test_ic_trigger.py
    ├── test_ic_adjuster.py
    ├── test_ic_safety.py
    ├── test_ic_exit.py
    └── test_ic_cycle.py

webui/frontend/src/components/ic/  ← new React components
├── ICContext.js                   ← React context + WebSocket listener
├── icService.js                   ← Axios API wrapper
├── hooks/
│   └── useICWebSocket.js          ← WebSocket hook (mirrors useMMMWebSocket)
├── ICDashboard.js                 ← Main dashboard (top-level)
├── ICSessionList.js               ← List of IC sessions
├── ICSessionCard.js               ← Summary card per session
├── ICConfigPanel.js               ← Create session / parameter form
├── ICLegTable.js                  ← 4-leg positions table
├── ICStrikeMap.js                 ← Visual strike map with price position
├── ICPnLChart.js                  ← Unrealized P&L over time
├── ICCycleHistory.js              ← Historical cycles with outcomes
├── ICAdjustmentLog.js             ← Log of all rolls/adjustments
├── ICStatusBanner.js              ← Session status, DTE countdown, margin
└── ICPayoffDiagram.js             ← Live payoff diagram with current price

webui/frontend/src/pages/
└── ICPage.js                      ← Top-level page (added to router)

webui/backend/data/
└── ic_sessions.json               ← Persistent session storage
```

**Route registration** (in `webui/backend/app.py`):
```python
from webui.backend.routes.ic.ic_api import ic_bp
app.register_blueprint(ic_bp)
```

---

## 4. State Model

### 4.1 Session State (top-level)

```python
{
  # Identity
  "id": "ic_20260324_001",          # Unique session ID
  "name": "BTC IC Weekly",          # Human name
  "created_at": "2026-03-24T...",
  "symbol": "BTCUSD",               # Underlying

  # Lifecycle
  "status": "RUNNING",              # IDLE | RUNNING | PAUSED | STOPPED
  "strategy_status": "ACTIVE",      # IDLE | ENTRY_PENDING | ACTIVE | ADJUSTING | EXIT_PENDING | EXITED | CYCLING

  # Cycle tracking
  "cycle_number": 1,                # Current cycle (increments after each close+reopen)
  "cycles_completed": 0,            # Historical closed cycles
  "total_realized_pnl": 0.0,        # Cumulative across all cycles (USD)

  # Current cycle
  "current_cycle": { ... },         # See §4.2 below — null if no active cycle

  # Params
  "params": { ... },                # See §5 below

  # Safety
  "safety_events": [],              # Recent safety events
  "daily_loss_usd": 0.0,            # Losses today (resets at UTC midnight)
  "max_daily_loss_hit": False,

  # Metadata
  "expiry": "2026-03-28",           # Current target expiry
  "last_heartbeat": "2026-03-24T...",
  "heartbeat_count": 0,
}
```

### 4.2 Current Cycle State

```python
"current_cycle": {
  # Identity
  "cycle_id": "cyc_001",
  "opened_at": "2026-03-24T10:00:00Z",
  "closed_at": None,                  # Set when cycle is closed
  "expiry": "2026-03-28",

  # Entry premiums (collected at open)
  "entry_net_credit": 45.50,          # USD per BTC = SP_premium + SC_premium - LP_premium - LC_premium
  "entry_net_credit_usd": 18.20,      # entry_net_credit × lots × 0.001

  # 4 legs — each leg has same structure
  "legs": {
    "SP": {                           # Short Put
      "strike": 82000,
      "lots": 10,
      "order_id": "...",
      "entry_premium": 28.0,          # USD/BTC at fill
      "mark_premium": 35.0,           # Current mark price
      "side": "put",
      "action": "sell",
      "status": "open",               # open | closed | rolled
      "fill_time": "2026-03-24T...",
      "close_premium": None,
    },
    "LP": {                           # Long Put (wing)
      "strike": 81000,
      "lots": 10,
      "order_id": "...",
      "entry_premium": 8.0,
      "mark_premium": 6.5,
      "side": "put",
      "action": "buy",
      "status": "open",
      "fill_time": "2026-03-24T...",
      "close_premium": None,
    },
    "SC": {                           # Short Call
      "strike": 88000,
      "lots": 10,
      "order_id": "...",
      "entry_premium": 30.0,
      "mark_premium": 22.0,
      "side": "call",
      "action": "sell",
      "status": "open",
      "fill_time": "2026-03-24T...",
      "close_premium": None,
    },
    "LC": {                           # Long Call (wing)
      "strike": 89000,
      "lots": 10,
      "order_id": "...",
      "entry_premium": 12.0,
      "mark_premium": 9.0,
      "side": "call",
      "action": "buy",
      "status": "open",
      "fill_time": "2026-03-24T...",
      "close_premium": None,
    },
  },

  # Computed values (updated every heartbeat)
  "spot_price": 85000.0,
  "max_profit_usd": 18.20,            # Fixed at entry = entry_net_credit_usd
  "max_loss_usd": -81.80,             # DYNAMIC: recalculated after each roll = (wing_width - effective_net_credit) × lots × 0.001
  "unrealized_pnl_usd": 5.40,         # Current mark-to-market P&L
  "pnl_as_pct_of_max_profit": 29.7,   # Percentage of max profit captured

  # Strikes summary (for quick access)
  "short_put_strike": 82000,
  "long_put_strike": 81000,
  "short_call_strike": 88000,
  "long_call_strike": 89000,
  "wing_width_put": 1000,             # SP - LP
  "wing_width_call": 1000,            # LC - SC

  # Adjustment history
  "adjustments": [],                  # List of adjustment events (see §9.4)
  "adjustment_count": 0,

  # Exit tracking
  "exit_reason": None,                # "profit_target" | "max_loss" | "dte_close" | "manual" | "rolled"
  "exit_pnl_usd": None,               # Realized P&L when closed
}
```

### 4.3 Cycle History

```python
"cycle_history": [
  {
    "cycle_id": "cyc_001",
    "opened_at": "...",
    "closed_at": "...",
    "entry_net_credit_usd": 18.20,
    "exit_pnl_usd": 9.10,            # 50% profit
    "exit_reason": "profit_target",
    "adjustment_count": 1,
    "max_adverse_excursion_usd": -12.0,
  },
  ...
]
```

---

## 5. Parameters

```python
DEFAULT_PARAMS = {
  # --- Entry ---
  "lots": 10,                         # Lots per leg (all 4 legs same size)
  "expiry_dte": 7,                     # Target days-to-expiry at entry
  "wing_width_strikes": 1,             # Number of strikes between short and long
                                       # (e.g., 1 = next strike, 2 = skip one)
  "wing_width_usd": 1000,             # Alternative: wing width in USD (takes priority if set)
  "short_put_delta_target": 0.16,     # Target delta for short put (0.16 = 1σ)
  "short_call_delta_target": 0.16,    # Target delta for short call
  "strike_interval": 500,             # BTC strike grid interval in USD (Delta Exchange uses 500)

  # --- Heartbeat ---
  "adjustment_interval": 60,          # Seconds between heartbeats
  "rapid_check_interval": 15,         # Faster interval when breach is near

  # --- Exit ---
  "profit_target_pct": 50,            # Close when unrealized P&L = X% of max credit
  "close_at_dte": 1,                   # Force-close when DTE falls below this
  "max_loss_pct": 100,                 # Force-close when loss = X% of max loss
                                       # (100% = at max loss boundary; 80% = earlier)

  # --- Adjustment Triggers ---
  "breach_pct": 5.0,                  # Trigger adjustment when spot is within X% of short strike
  "roll_tested_side_enabled": True,   # Auto-roll the threatened spread
  "roll_untested_side_enabled": True, # Also roll untested side closer for extra credit
  "max_adjustments_per_cycle": 3,     # Hard cap on rolls per cycle
  "adjustment_cooldown_sec": 300,     # Min seconds between adjustments

  # --- New Cycle ---
  "auto_cycle": True,                 # Automatically open next cycle after close
  "cycle_delay_sec": 30,              # Wait N seconds between close and next entry
  "same_expiry_after_roll": True,     # Keep same expiry after roll (vs pick new one)

  # --- Safety ---
  "max_daily_loss_usd": 500,          # Stop trading today if total loss exceeds this
  "margin_safety_pct": 20,            # Pause if available margin < X% of required margin
  "circuit_breaker_enabled": True,    # Pause if 3+ adjustments in 1 hour

  # --- Entry Quality ---
  "min_net_credit_per_btc": 10.0,    # Reject entry if net credit < this (USD/BTC)
  "min_credit_to_wing_ratio": 0.03,  # Net credit must be ≥ 3% of wing width

  # --- Mode ---
  "simulate": False,                  # True = log decisions without placing real orders (see §C.9)
}

# Hot-reload params (can be changed without stopping session)
HOT_RELOAD_PARAMS = [
  "adjustment_interval", "rapid_check_interval",
  "profit_target_pct", "close_at_dte", "max_loss_pct",
  "breach_pct", "max_adjustments_per_cycle", "adjustment_cooldown_sec",
  "auto_cycle", "cycle_delay_sec",
  "max_daily_loss_usd", "margin_safety_pct",
]
```

---

## 6. Algorithm Phases — Heartbeat Design

### 6.1 High-Level Heartbeat Flow

```
Every `adjustment_interval` seconds:

┌─────────────────────────────────────────────────────┐
│  PHASE 0: Safety gate                               │
│  - Check daily loss limit                           │
│  - Check margin available                           │
│  - Check circuit breaker                            │
│  → If blocked: emit safety event, skip to end       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 1: Fetch market data                         │
│  - Spot price (BTC/USD)                             │
│  - Mark prices for all 4 legs                       │
│  - Time to expiry (minutes / DTE)                   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 2: Compute live P&L + Greeks                  │
│  - unrealized_pnl per leg = (entry - mark) × sign  │
│  - total unrealized_pnl_usd                         │
│  - pnl_as_pct_of_max_profit                         │
│  - Portfolio Greeks: Δ, Γ, Θ, V (see §C.4)         │
│  - Recalc max_loss if rolls occurred (see §8.2)     │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 2.5: Expiry check                            │
│  - if current_time >= expiry_time → handle expiry   │
│  - Mark legs as expired, compute settlement P&L     │
│  - See §C.5 for details                             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 3: Exit checks (before adjustment)           │
│  A. Profit target hit?  → ic_exit.close_cycle()     │
│  B. Max loss hit?       → ic_exit.close_cycle()     │
│  C. DTE too low?        → ic_exit.close_cycle()     │
│  → If exited: trigger new cycle if auto_cycle=True  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 4: Entry check (if no active cycle)          │
│  - strategy_status == IDLE or CYCLING               │
│  - Select strikes → ic_strike_selector              │
│  - Place 4 orders → ic_executor                     │
│  - Update state to ACTIVE                           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 5: Breach detection (if ACTIVE cycle)        │
│  - is_put_side_threatened(spot, SP, breach_pct)?    │
│  - is_call_side_threatened(spot, SC, breach_pct)?   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 6: Adjustment decision                       │
│  - Check adjustment cooldown                        │
│  - Check max_adjustments_per_cycle                  │
│  - Determine roll type (see §9)                     │
│  - Execute roll via ic_roller                       │
│  - Log adjustment event                             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  PHASE 7: Emit & persist                            │
│  - Emit WebSocket heartbeat event                   │
│  - Emit P&L update                                  │
│  - Save session to ic_sessions.json                 │
└─────────────────────────────────────────────────────┘
```

### 6.2 Rapid-Check Mode

When spot is within `2 × breach_pct` of any short strike, switch heartbeat to `rapid_check_interval` (default 15s).
Returns to normal interval when spot moves back to center.

---

## 7. Entry Logic — Strike & Wing Selection

### 7.1 Algorithm

```
Input: spot_price, expiry, params

1. Fetch available strikes from Delta Exchange:
   GET /products?contract_types=call_options,put_options&underlying_asset_symbol=BTC
   Filter by expiry → get sorted list of available strike prices
   (Do NOT assume fixed $500 intervals — strike grid varies by distance from ATM)

2. Short Put strike selection (using REAL delta from API):
   For each available put strike below spot:
     Fetch delta from GET /tickers/{symbol} or cached WS data
   SP = strike where |delta| is closest to short_put_delta_target (e.g., 0.16)

3. Long Put strike:
   LP = nearest available strike at or beyond (SP - wing_width_usd) distance
   Ensure LP < SP and actual wing ≥ wing_width_usd

4. Short Call strike selection (using REAL delta from API):
   For each available call strike above spot:
     Fetch delta from ticker data
   SC = strike where |delta| is closest to short_call_delta_target (e.g., 0.16)

5. Long Call strike:
   LC = nearest available strike at or beyond (SC + wing_width_usd) distance
   Ensure LC > SC and actual wing ≥ wing_width_usd

6. Validate:
   - LP < SP < spot < SC < LC (strict ordering)
   - Net credit > 0 (fetch live bid/ask for all 4 legs)
   - Net credit ≥ min_net_credit_per_btc (reject if credit too thin — see §C.6)
   - Net credit / wing_width ≥ min_credit_to_wing_ratio (risk:reward sanity)
   - Wing width > 0 on both sides

7. Use POST /v2/orders/batch for all 4 legs simultaneously (see §C.3)
   Handle partial fills via atomicity protocol (see §C.1)

8. Return: (LP_strike, SP_strike, SC_strike, LC_strike, actual_net_credit)
```

**Note on vol skew:** Crypto puts are typically more expensive than calls at equal delta. This means SP may be closer to spot than SC. The condor will be naturally asymmetric — this is expected and correct (see §C.10).

### 7.2 Strike Re-centering After Roll

After an adjustment roll, the condor is no longer symmetric. Track effective center:
```
effective_center = (SP_active + SC_active) / 2
```
This is displayed in the UI and used for proximity calculations.

---

## 8. P&L Formulas

### 8.1 Max Profit (fixed at entry)
```
max_profit_per_btc = entry_net_credit        # USD per BTC
max_profit_usd = max_profit_per_btc × lots × LOT_SIZE_BTC
```

### 8.2 Max Loss (DYNAMIC — recalculated after each roll)
```
wing_width_per_btc = SP_strike - LP_strike   # USD (same for call side ideally)
max_loss_per_btc = wing_width_per_btc - effective_net_credit
max_loss_usd = max_loss_per_btc × lots × LOT_SIZE_BTC   (negative — it's a loss)

CRITICAL: max_loss is NOT fixed. After each roll:
  effective_net_credit = entry_net_credit + cumulative_roll_credit
  → If roll costs debit: effective_net_credit decreases → max_loss INCREASES
  → If roll collects credit: effective_net_credit increases → max_loss DECREASES

This must be recalculated in ic_engine.py after every adjustment.
```

### 8.2.1 Max Loss After Asymmetric Wing Roll
```
If a roll changes only one side, the two wings may have different widths:
  wing_put  = SP_strike - LP_strike
  wing_call = LC_strike - SC_strike

  max_loss_per_btc = max(wing_put, wing_call) - effective_net_credit
  (Use the WIDER wing — that's the true worst-case.)
```

### 8.3 Unrealized P&L (updated every heartbeat)
```
For each leg:
  if leg.action == 'sell':
    leg_pnl_per_btc = leg.entry_premium - leg.mark_premium  (positive if premium fell)
  if leg.action == 'buy':
    leg_pnl_per_btc = leg.mark_premium - leg.entry_premium  (positive if premium fell)

total_pnl_per_btc = sum(leg_pnl_per_btc for all legs)
unrealized_pnl_usd = total_pnl_per_btc × lots × LOT_SIZE_BTC
```

### 8.4 P&L as % of Max Profit
```
pnl_pct = (unrealized_pnl_usd / max_profit_usd) × 100
```
- At 50%: profit target (default exit)
- At 100%: max profit achieved (condor fully expired worthless)
- At -X%: where X% = (|max_loss_usd| / max_profit_usd) × 100: max loss

### 8.5 Realized P&L on Close
```
For each leg closed:
  if sell: realized = (entry_premium - close_premium) × lots × LOT_SIZE_BTC
  if buy:  realized = (close_premium - entry_premium) × lots × LOT_SIZE_BTC

cycle_realized_pnl = sum(all legs)
```

### 8.6 All-time Cumulative
```
total_realized_pnl += cycle_realized_pnl   (updated after each cycle close)
```

---

## 9. Adjustment Logic — The Auto-Adjustment Mind

This is the core intelligence that makes this algo continuously adaptive.

### 9.1 Breach Detection

```python
def is_call_side_threatened(spot, SC_strike, breach_pct) -> bool:
    distance_pct = (SC_strike - spot) / spot * 100
    return distance_pct <= breach_pct   # e.g., spot within 5% of SC

def is_put_side_threatened(spot, SP_strike, breach_pct) -> bool:
    distance_pct = (spot - SP_strike) / spot * 100
    return distance_pct <= breach_pct
```

### 9.2 Adjustment Decision Tree

```
Both sides threatened?
  → Emergency: close entire condor NOW, re-enter after cooldown

Only call side threatened (spot moved up)?
  → Action A: Roll Call Spread Up
     Close SC + LC at market
     Reopen SC' (new higher strike) + LC' (SC' + wing_width)
     If roll_untested_side_enabled:
       Also roll put spread: close SP + LP, reopen at higher center

Only put side threatened (spot moved down)?
  → Action B: Roll Put Spread Down
     Close SP + LP at market
     Reopen SP' (new lower strike) + LP' (SP' - wing_width)
     If roll_untested_side_enabled:
       Also roll call spread: close SC + LC, reopen at lower center

No breach?
  → No action (continue monitoring)
```

### 9.3 Roll Execution (ic_roller.py)

```
Roll of one spread (e.g., call side):
  Step 1: Close SC (buy back short call) — limit order at ask
  Step 2: Close LC (sell long call) — limit order at bid
  Step 3: Wait for both fills (up to 60s each, amend if needed)
  Step 4: Select new SC' and LC' strikes
  Step 5: Sell SC' — limit order at bid
  Step 6: Buy LC' — limit order at ask
  Step 7: Update leg state (SC → status='rolled', new SC' appended as active SC)

Roll credit/debit:
  roll_credit = (SC_close_price + LC_close_price × -1)
              + (SC'_entry_price + LC'_entry_price × -1)
  (positive = collected more credit, negative = paid debit for roll)

  Accumulated in: cycle.cumulative_roll_credit
```

### 9.4 Adjustment Event Record

```python
{
  "event_id": "adj_001",
  "timestamp": "...",
  "type": "roll_call_up",              # roll_call_up | roll_put_down | roll_both | emergency_close
  "trigger": "breach_call",
  "spot_at_trigger": 87800.0,
  "old_strikes": {"SC": 88000, "LC": 89000},
  "new_strikes": {"SC": 89000, "LC": 90000},
  "roll_credit": -5.20,                # Negative = paid debit for roll
  "cumulative_roll_credit": -5.20,
}
```

### 9.5 Adjustment Guardrails

- **max_adjustments_per_cycle**: if reached, go to EXIT_PENDING instead of adjusting
- **adjustment_cooldown_sec**: minimum time between any two adjustments (prevents rapid re-rolls on volatile chop)
- **circuit_breaker**: if 3 adjustments in 60 minutes → pause session, alert operator
- **Emergency close threshold**: if both sides are threatened simultaneously, close immediately regardless of guardrails (safety overrides all)
- **Near-expiry guard**: if DTE < `close_at_dte + 1`, refuse roll — close cycle instead (gamma death zone — see §C.7)
- **Negative credit guard**: if roll would make `effective_net_credit ≤ 0`, refuse roll — close cycle instead (guaranteed loss — see §C.2)

### 9.6 Net Credit After Rolls

After rolls, track effective entry credit:
```
effective_net_credit = entry_net_credit + cumulative_roll_credit
```
All P&L percentages (profit target, etc.) recalculate against this effective credit.

---

## 10. Exit Logic & Cycle Management

### 10.1 Exit Conditions (checked in order, every heartbeat)

```
Priority 1 — Emergency: Both sides threatened simultaneously
  → Close all 4 legs immediately
  → exit_reason = "emergency_close"

Priority 2 — Max Loss
  → |unrealized_pnl_usd| >= |max_loss_usd| × (max_loss_pct/100)
  → Close all 4 legs
  → exit_reason = "max_loss"

Priority 3 — DTE Close
  → minutes_to_expiry <= (close_at_dte × 1440)
  → Close all 4 legs (gamma risk too high at expiry)
  → exit_reason = "dte_close"

Priority 4 — Profit Target
  → pnl_as_pct_of_max_profit >= profit_target_pct
  → Close all 4 legs
  → exit_reason = "profit_target"
```

### 10.2 Close Sequence (ic_exit.py)

```
1. For each leg (in optimal order: buy-back short legs first):
   SP: place buy order (limit at ask, amend until filled)
   SC: place buy order (limit at ask, amend until filled)
   LP: place sell order (limit at bid, amend until filled)
   LC: place sell order (limit at bid, amend until filled)

2. Calculate cycle_realized_pnl

3. Update session:
   current_cycle.closed_at = now
   current_cycle.exit_reason = exit_reason
   current_cycle.exit_pnl_usd = cycle_realized_pnl
   cycles_completed += 1
   total_realized_pnl += cycle_realized_pnl
   daily_loss_usd += min(0, cycle_realized_pnl)

4. Move current_cycle → cycle_history

5. Emit WebSocket: ic_cycle_closed

6. If auto_cycle and not daily_loss_hit and not circuit_break:
   strategy_status = "CYCLING"
   Schedule entry after cycle_delay_sec
```

### 10.3 New Cycle Entry

```
1. Wait cycle_delay_sec
2. Determine expiry for next cycle (same expiry if DTE remaining, else next weekly)
3. Run strike selection for new expiry
4. Validate quotes are live
5. Place 4 orders → new current_cycle
6. strategy_status = "ACTIVE"
7. cycle_number += 1
8. Emit: ic_cycle_opened
```

---

## 11. Safety System

Simpler than MMM because losses are defined. Three layers:

### Layer 1 — Session-level Hard Stops

| Check | Condition | Action |
|-------|-----------|--------|
| Daily loss limit | `daily_loss_usd` >= `max_daily_loss_usd` | Stop session for today; resume next UTC day |
| Margin check | Available margin < `margin_safety_pct`% of required | Pause session; alert Telegram |
| Data confidence | >3 consecutive premium fetch failures | Pause session; alert; resume when data returns |

### Layer 2 — Cycle-level Hard Stops

| Check | Condition | Action |
|-------|-----------|--------|
| Max loss | `pnl_usd <= max_loss_usd × (max_loss_pct/100)` | Emergency close |
| Max adjustments | `adjustment_count >= max_adjustments_per_cycle` | Exit cycle, no more adjustments |
| Emergency breach | Both sides threatened | Emergency close immediately |

### Layer 3 — Circuit Breaker

| Check | Condition | Action |
|-------|-----------|--------|
| Rapid adjustment storm | 3+ adjustments in 60 min | Pause 30 min, alert operator |
| Fill timeout cascade | 3 consecutive order fills timed out | Pause, alert |

### Safety Event Format

```python
{
  "type": "daily_loss_limit",
  "level": "critical",              # info | warning | alert | critical
  "message": "Daily loss $520 exceeds limit $500",
  "action": "stop",                 # continue | warn | pause | stop
  "timestamp": "...",
}
```

---

## 12. API Design

### Blueprint

```python
ic_bp = Blueprint('ic', __name__, url_prefix='/api/ic')
```

### Endpoints

```
Session Management:
  GET    /api/ic/sessions              → list all sessions
  POST   /api/ic/sessions              → create new session
  GET    /api/ic/sessions/<id>         → get session detail
  DELETE /api/ic/sessions/<id>         → delete session

Session Control:
  POST   /api/ic/sessions/<id>/start   → start monitoring (auto-entry)
  POST   /api/ic/sessions/<id>/pause   → pause heartbeat
  POST   /api/ic/sessions/<id>/resume  → resume heartbeat
  POST   /api/ic/sessions/<id>/stop    → stop + close all open legs

Params:
  GET    /api/ic/sessions/<id>/params  → get current params
  PATCH  /api/ic/sessions/<id>/params  → hot-reload params (no restart)

Manual Control:
  POST   /api/ic/sessions/<id>/close   → manually close current cycle
  POST   /api/ic/sessions/<id>/roll    → manually trigger a roll
  POST   /api/ic/sessions/<id>/skip_cycle → skip next auto-entry

Diagnostics:
  GET    /api/ic/sessions/<id>/pnl     → live P&L for all legs
  GET    /api/ic/sessions/<id>/health  → heartbeat health, last beat time
  GET    /api/ic/sessions/<id>/history → cycle history list
```

---

## 13. WebSocket Events

All events emitted to the `ic` namespace or as `ic_*` event names on the main namespace.

```
ic_heartbeat          → { session_id, spot, legs_pnl, unrealized_pnl, pnl_pct, dte, status }
ic_pnl_update         → { session_id, unrealized_pnl_usd, pnl_pct, max_profit_usd, max_loss_usd }
ic_cycle_opened       → { session_id, cycle_id, cycle_number, legs: {SP,LP,SC,LC}, net_credit_usd }
ic_cycle_closed       → { session_id, cycle_id, exit_reason, realized_pnl_usd, total_realized_pnl }
ic_adjustment_started → { session_id, type, trigger, old_strikes, estimated_roll_credit }
ic_adjustment_done    → { session_id, type, new_strikes, roll_credit, adjustment_count }
ic_breach_alert       → { session_id, side: 'call'|'put'|'both', spot, short_strike, distance_pct }
ic_safety_event       → { session_id, type, level, message, action }
ic_status_change      → { session_id, old_status, new_status }
ic_rapid_check_on     → { session_id, reason, side }
ic_rapid_check_off    → { session_id }
```

---

## 14. WebUI Design

### 14.1 Navigation

Add "Iron Condor" tab to the existing navigation bar alongside "MMM".

### 14.2 ICPage Layout (Top Level)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Navigation: [...] | MMM | Iron Condor | Options | ...              │
├─────────────────────────────────────────────────────────────────────┤
│  ICPage                                                             │
│  ┌─────────────────────────────┐  ┌───────────────────────────────┐ │
│  │  Session List (left panel)  │  │  Session Detail (right panel) │ │
│  │                             │  │                               │ │
│  │  + New IC Session           │  │  [selected session content]   │ │
│  │                             │  │                               │ │
│  │  ● BTC Weekly IC            │  │                               │ │
│  │    RUNNING | Cycle 3        │  │                               │ │
│  │    +$45.20 today            │  │                               │ │
│  │                             │  │                               │ │
│  │  ○ BTC 0DTE IC              │  │                               │ │
│  │    STOPPED | 12 cycles      │  │                               │ │
│  └─────────────────────────────┘  └───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.3 Session Detail Panel (Right Side)

```
┌─────────────────────────────────────────────────────────────────────┐
│  BTC Weekly IC  ● RUNNING | Cycle 3 | Expiry: Mar 28 (4d 6h)       │
│  [▶ Pause]  [⬜ Stop]  [⚙ Settings]  [↺ Refresh]                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  STATUS BANNER (ICStatusBanner)                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  BTC: $85,420  |  DTE: 4.26  |  Interval: 60s  |  ✓ Healthy │   │
│  │  [ACTIVE — waiting for exit trigger]                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Max Profit      │  │  Unrealized P&L  │  │  Max Loss        │  │
│  │  +$18.20         │  │  +$9.40  (51.6%) │  │  -$81.80         │  │
│  │  per cycle       │  │  ████████░░ 52%  │  │  hard cap        │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  TABS: [Positions] [Strike Map] [Payoff] [P&L Chart] [Adjustments]  │
│        [Cycle History] [Settings]                                   │
├─────────────────────────────────────────────────────────────────────┤
│  [Positions Tab — default]                                          │
│                                                                     │
│  LEG TABLE (ICLegTable)                                             │
│  ┌──────┬────────┬──────┬───────────┬──────────┬──────┬──────────┐  │
│  │ Leg  │ Side   │ Act  │ Strike    │ Entry    │ Mark │ Leg P&L  │  │
│  ├──────┼────────┼──────┼───────────┼──────────┼──────┼──────────┤  │
│  │ LP   │ Put    │ Buy  │ 81,000    │ $8.00    │$6.80 │ +$0.12   │  │
│  │ SP ★ │ Put    │ Sell │ 82,000    │ $28.00   │$22.0 │ +$0.60   │  │
│  │ SC ★ │ Call   │ Sell │ 88,000    │ $30.00   │$22.5 │ +$0.75   │  │
│  │ LC   │ Call   │ Buy  │ 89,000    │ $12.00   │$9.80 │ +$0.22   │  │
│  ├──────┴────────┴──────┴───────────┴──────────┴──────┼──────────┤  │
│  │ Net credit at entry: $38.00/BTC × 10 lots = $3.80  │ +$9.40  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ★ = short leg (risk leg)                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.4 Strike Map Tab (ICStrikeMap)

```
ICStrikeMap — Visual price axis with condor wings

BTC: $85,420

  $81,000  LP ─────[PUT WING]──── SP $82,000

  $82,000  SP ━━━━━━━━━━━━━━━━━━━ [PROFIT ZONE] ━━━━━ SC $88,000

  ← 3.96% distance →            ← 3.00% distance →

  ▲ BTC NOW: $85,420 ──────────────────────────────────→

  $88,000  SC ─────[CALL WING]─── LC $89,000

  Proximity bars:
  PUT side:  [████████████░░░░░░░░]  3.96% away  [SAFE — green]
  CALL side: [████████████████░░░░]  3.00% away  [WATCH — yellow]

  Breach at: 5.00% → adjust trigger
  Rapid at:  10.0% → fast heartbeat
```

Color coding:
- Green: distance > 2× breach_pct
- Yellow: distance between 1-2× breach_pct
- Red: distance < breach_pct (adjustment will trigger)

### 14.5 Payoff Diagram Tab (ICPayoffDiagram)

```
Payoff at expiry (X = BTC price, Y = P&L in USD)

  +$18.20 ┤     ████████████████████
          ┤   ██                    ██
    $0.00 ┼─██────────────────────────██─────→ BTC price
          ┤ █                          █
  -$81.80 ┤█                            █
          │
         LP     SP    NOW     SC      LC
        81000  82000  85420  88000  89000

  Live P&L marker: ● (updates every heartbeat)
  Entry: show both "at expiry" line AND "current mark" line
```

### 14.6 P&L Chart Tab (ICPnLChart)

```
Unrealized P&L over time (current cycle)
Y: USD P&L
X: Time since cycle opened

+$18.20 ─────────────────────── MAX PROFIT (dashed green)

+$9.10 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 50% TARGET (dashed orange)

         /\_____/\___/\___  current P&L trace
    $0 ──

-$81.80 ─────────────────────── MAX LOSS (dashed red)

  [Toggle: Current Cycle | All Cycles | Cumulative]
```

### 14.7 Adjustments Tab (ICAdjustmentLog)

```
Adjustment History — Cycle 3

  [No adjustments yet]

─── Cycle 2 ─────────────────────────────────────────────────────────

  2026-03-24 10:42  ROLL_CALL_UP
  Trigger: Spot $87,850 within 0.17% of SC $88,000 (breach: 5%)
  Old: SC=88,000 / LC=89,000
  New: SC=89,000 / LC=90,000
  Roll debit paid: -$3.20/BTC = -$0.32 USD
  Net credit after roll: $34.80/BTC

─────────────────────────────────────────────────────────────────────
```

### 14.8 Cycle History Tab (ICCycleHistory)

```
Cycle History

 Cycle │ Opened       │ Closed       │ Exit Reason    │ P&L       │ Adj
───────┼──────────────┼──────────────┼────────────────┼───────────┼─────
  3    │ Running...   │ —            │ —              │ +$9.40*   │  0
  2    │ Mar 23 10:00 │ Mar 23 14:22 │ profit_target  │ +$9.10    │  1
  1    │ Mar 22 10:00 │ Mar 23 09:55 │ dte_close      │ +$6.40    │  0
───────┴──────────────┴──────────────┴────────────────┴───────────┴─────
  Total realized P&L: +$24.90   (*unrealized)
```

### 14.9 Settings Tab (ICConfigPanel)

```
Settings — BTC Weekly IC

  General
  ├─ Lots per leg:         [ 10 ]
  ├─ Target DTE at entry:  [ 7  ]
  └─ Wing width (USD):     [ 1000 ]

  Strike Selection
  ├─ Short put delta:      [ 0.16 ]
  ├─ Short call delta:     [ 0.16 ]
  └─ Strike grid interval: [ 500 ]

  Heartbeat
  ├─ Normal interval (s):  [ 60 ]
  └─ Rapid interval (s):   [ 15 ]

  Exit Rules
  ├─ Profit target (%):    [ 50 ]
  ├─ Close at DTE (days):  [ 1  ]
  └─ Max loss (%):         [ 100 ]

  Adjustment
  ├─ Breach threshold (%): [ 5.0 ]
  ├─ Roll tested side:     [✓]
  ├─ Roll untested side:   [✓]
  ├─ Max adj/cycle:        [ 3  ]
  └─ Adj cooldown (s):     [ 300 ]

  Auto-Cycle
  ├─ Auto-cycle:           [✓]
  └─ Cycle delay (s):      [ 30 ]

  Safety
  ├─ Max daily loss (USD): [ 500 ]
  └─ Margin safety (%):    [ 20  ]

  [Save Changes]  [Reset to Defaults]
  (Changes to highlighted fields take effect immediately — no restart needed)
```

### 14.10 Create Session Dialog

```
New Iron Condor Session

  Session Name:    [BTC Weekly IC          ]
  Symbol:          [BTCUSD          ▼]
  Target Expiry:   [2026-03-28      ▼]  (shows available expiries)

  Quick Presets:
  [0DTE Aggressive]  [Weekly Conservative]  [Weekly Balanced]
                                             ← selected

  Estimated at current prices:
  Short Put:  ~$82,000   Short Call:  ~$88,000
  Long Put:   ~$81,000   Long Call:   ~$89,000
  Est. Credit: ~$38/BTC  Max Loss: ~$962/BTC
  Credit for 10 lots: ~$3.80 USD

  [Cancel]  [Create & Start]
```

---

## 15. Testing Plan

### Unit Tests (ic/tests/)

| File | Tests |
|------|-------|
| `test_ic_engine.py` | net_credit calc, max_loss calc, unrealized_pnl per leg, realized on close, Decimal precision |
| `test_ic_strike_selector.py` | LP < SP < SC < LC invariant, wing width, symmetric wings, delta targeting |
| `test_ic_trigger.py` | breach_pct detection call/put/both, rapid-check mode threshold |
| `test_ic_adjuster.py` | roll call up, roll put down, emergency close trigger, cooldown respected, max_adj respected |
| `test_ic_safety.py` | daily loss limit, margin check, circuit breaker, data confidence |
| `test_ic_exit.py` | profit target exit, max_loss exit, dte_close exit, priority ordering |
| `test_ic_cycle.py` | auto_cycle=True opens next cycle, auto_cycle=False stays IDLE, delay respected |

### Integration Tests

- Full heartbeat loop: entry → ACTIVE → breach → roll → profit target → close → new cycle
- Emergency close: both sides breached simultaneously
- Max adjustments: 3 rolls then exit on 4th breach
- Daily loss: session stops after daily_loss_usd exceeded

---

## 16. Implementation Phases

### Phase 1 — Core Backend (no UI, no live orders) ✅ COMPLETE
**Deliverable:** All Python modules written + unit tests passing, with a simulate mode that prints decisions without placing real orders.

**Status:** All 14 files implemented. 49 unit tests passing.

Files (all in `webui/backend/routes/ic/`):
- ✅ `ic_constants.py` — Leg IDs, status enums, exit/safety constants (93 LOC)
- ✅ `ic_state.py` — Session, cycle, leg state creation + helpers (247 LOC)
- ✅ `ic_config.py` — 27 params, validation rules, hot-reload support (215 LOC)
- ✅ `ic_storage.py` — SQLite with WAL mode, UPSERT, atomic updates (234 LOC)
- ✅ `ic_engine.py` — All P&L formulas: net credit, dynamic max loss, unrealized, roll credit (195 LOC)
- ✅ `ic_strike_selector.py` — Delta-targeted strike selection with quality gates (265 LOC)
- ✅ `ic_greeks.py` — Portfolio-level Greek aggregation with sign semantics (86 LOC)
- ✅ `ic_trigger.py` — Breach detection using distance-from-strike % (107 LOC)
- ✅ `ic_safety.py` — 3-layer safety: session → cycle → circuit breaker (215 LOC)
- ✅ `ic_exit.py` — Priority-ordered exits: emergency → max loss → DTE → profit (175 LOC)
- ✅ `ic_cycle.py` — Cycle lifecycle: open → monitor → close → repeat (175 LOC)
- ✅ `ic_adjuster.py` — Decision tree + guardrails: cooldown, max adj, negative credit, gamma guard (198 LOC)
- ✅ `__init__.py` — Module init (8 LOC)
- ✅ `tests/test_ic_core.py` — 49 unit tests across 9 test classes (410 LOC)

### Phase 2 — Execution + Monitor ✅ COMPLETE
**Deliverable:** Real orders can be placed. Heartbeat loop runs. Session survives backend restart.

**Status:** All 4 files implemented. Simulate mode fully functional.

Files (all in `webui/backend/routes/ic/`):
- ✅ `ic_executor.py` — Batch order placement with simulate mode + atomicity framework (216 LOC)
- ✅ `ic_roller.py` — Roll execution for call-up and put-down adjustments (190 LOC)
- ✅ `ic_monitor.py` — 7-phase heartbeat loop in daemon thread (252 LOC)
- ✅ `ic_activity.py` — Activity logging with `algo='ic'` tag (78 LOC)

### Phase 3 — API + WebSocket ✅ COMPLETE
**Deliverable:** REST API wired up, WebSocket events emitting. Testable via curl/Postman.

**Status:** All 4 files implemented. Blueprint registered in `app.py`.

Files (all in `webui/backend/routes/ic/`):
- ✅ `ic_websocket.py` — WS emit helpers with `ic_`-prefixed events, failure tracking (200 LOC)
- ✅ `ic_api.py` — Full Flask Blueprint: CRUD, lifecycle, params, cycles, activities (480 LOC)
- ✅ `ic_telegram.py` — Telegram alerts for all critical events with dedup (220 LOC)
- ✅ `__init__.py` — Updated with `init_ic()` session restore on startup (70 LOC)
- ✅ Blueprint registered in `app.py` — same pattern as MMM

### Phase 4 — WebUI ✅ COMPLETE
**Deliverable:** Full React dashboard, all tabs, real-time updates.

**Status:** All 13 files implemented. Route at `/ic`, sidebar nav entry added.

Files (in `webui/frontend/src/components/ic/`):
- ✅ `icService.js` — API client for `/api/ic` endpoints (110 LOC)
- ✅ `ICContext.js` — State management + WS listeners + polling (250 LOC)
- ✅ `ICDashboard.js` — Main dashboard: session list, P&L banner, 7-tab content, create dialog (310 LOC)
- ✅ `ICLegTable.js` — 4-leg position table: LP/SP/SC/LC with entry/mark/P&L (105 LOC)
- ✅ `ICStrikeMap.js` — Visual strike map with put/call wings, profit zone, proximity bars (120 LOC)
- ✅ `ICPayoffDiagram.js` — Payoff at expiry chart using Recharts (110 LOC)
- ✅ `ICPnLChart.js` — P&L over time chart with current/cumulative toggle (95 LOC)
- ✅ `ICAdjustmentLog.js` — Roll/adjustment history grouped by cycle (100 LOC)
- ✅ `ICCycleHistory.js` — Cycle history table with realized/unrealized P&L (115 LOC)
- ✅ `ICConfigPanel.js` — Parameter management with 7 groups, dirty tracking, hot-reload (170 LOC)
- ✅ `ICErrorBoundary.js` — Error boundary (45 LOC)
- ✅ `index.js` — Barrel exports (15 LOC)

Integration files:
- ✅ `ICPage.js` — Page wrapper in `webui/frontend/src/pages/`
- ✅ Route registered in `App.js` at `/ic`
- ✅ Sidebar nav entry in `navigationSections.js` under Algorithms group

### Phase 5 — Testing & Hardening
**Deliverable:** Testnet run for 48h. All edge cases validated.

- Run on Delta Exchange testnet for 2+ complete cycles
- Verify roll execution fills correctly
- Verify emergency close sequence
- Verify auto-cycle timing
- Verify state persistence across backend restart
- Check Telegram alerts

---

## 17. What We Reuse from MMM

| Component | Reuse level | Notes |
|-----------|-------------|-------|
| `mmm_constants.py` → `LOT_SIZE_BTC`, `strike_key` | Direct import | Both algos use same lot size |
| `mmm_executor.py` smart execution pattern | Copy + adapt | ic_executor mirrors the retry/amend logic |
| `mmm_storage.py` JSON storage pattern | Copy + adapt | Different schema, same file-lock pattern |
| `mmm_monitor.py` thread+heartbeat pattern | Mirror architecture | ic_monitor is structurally identical |
| `mmm_safety.py` safety event format | Mirror format | Same `{type, level, message, action}` dict |
| `mmm_websocket.py` emit helper pattern | Mirror | Different event names/payloads |
| `mmm_activity.py` activity log | Direct import if possible | Share activity log or have separate |
| `MMMMonitor` HeartbeatHealth + CircuitBreaker | Direct import | Module-level, no MMM state dependency |
| Frontend MUI components (Tabs, Tables, Charts) | Same library | ICDashboard uses same design language as MMMDashboard |
| Frontend useMMMWebSocket hook pattern | Mirror | useICWebSocket follows same structure |
| `sealed` decorator | Direct import | All core functions sealed same way |

**Do NOT reuse:**
- MMM trigger system (percentage-of-premium logic — IC uses distance-from-strike logic)
- MMM adjustment engine (sell-more-lots logic — IC uses roll-the-spread logic)
- MMM state (CE/PE lots ledger — IC uses 4-leg ledger)
- MMM P&L formulas (IC net credit formula is completely different)

---

## Appendix A — IC vs MMM Parameter Comparison

| MMM param | IC equivalent | Change |
|-----------|--------------|--------|
| `lots_per_side` | `lots` (applies to all 4 legs) | Single value |
| `adjustment_interval` | `adjustment_interval` | Same concept |
| `min_trigger_move` (% premium) | `breach_pct` (% distance to strike) | Different math |
| `max_loss_usd` | `max_loss_pct` (% of wing-width) | Defined, not absolute |
| `max_adjustments` | `max_adjustments_per_cycle` | Same concept |
| `close_at_dte` | `close_at_dte` | Same |
| N/A | `profit_target_pct` | New — IC has defined profit target |
| N/A | `wing_width_usd` | New — the core IC parameter |
| N/A | `auto_cycle` | New — continuous cycle management |

---

## Appendix B — Open Questions Before Implementation

1. **Delta Exchange delta data**: Does the API return per-leg delta values for options? If not, use approximation formula `delta ≈ N(d1)` with ATM IV as proxy.

2. **Strike grid**: Delta Exchange BTC options use $500 intervals? Confirm before coding `strike_interval=500` default.

3. **Expiry availability**: Are weekly expiries available on Delta Exchange India? Confirm available DTE options.

4. **Simultaneous 4-leg order**: Can 4 orders be placed in rapid succession and all fill reliably? Or use a combo/strategy order if available?

5. **Wing width choice**: Fixed USD (`wing_width_usd=1000`) vs fixed strike count (`wing_width_strikes=1`) — operator to decide default. Recommend `wing_width_usd` as primary since it directly sets the max loss in dollar terms.

6. **Lot sizing**: Should all 4 legs always be equal lots? (Yes — an unequal IC creates unwanted delta bias.)
**All questions answered by operator (2026-03-24). Summary of answers:**

| Q# | Topic | Answer | Impact on plan |
|----|-------|--------|----------------|
| 1 | Delta data | API returns greeks (delta/gamma/theta/vega) via REST and WS | Use real delta, no approximation needed. Add Greeks monitoring. |
| 2 | Strike grid | $500 intervals confirmed, may vary at far OTM | Fetch chain dynamically, don't hardcode. |
| 3 | Weekly expiry | Daily/Weekly/Monthly available | All DTE modes supported. |
| 4 | 4-leg order | No native combo. Use `POST /v2/orders/batch` (up to 50 orders) | Batch all legs. Add atomicity handling. |
| 5 | Wing width | Use `wing_width_usd` (direct risk control) | Confirmed as primary. |
| 6 | Lot sizing | Equal lots, integer only, 0.001 BTC/lot | Confirmed. |

---

## Appendix C — Critical Design Additions (Post-Review)

The following 12 items were identified during deep review. Items marked **CRITICAL** will lose money if not implemented. Items marked **IMPORTANT** prevent operational failures.

---

### C.1 CRITICAL: Partial Fill Atomicity

**The problem:** We place 4 orders for entry (or 4 for close, 4 for roll). What happens if only 2 fill and 2 get stuck/rejected? We're left with a broken structure — e.g., a naked short call without its long wing protection.

**Solution — Entry Atomicity via `ic_executor.py`:**

```
Entry:
  1. Use POST /v2/orders/batch for all 4 legs
  2. Monitor fills with 90-second per-leg timeout (amend if needed)
  3. Track fill state: NONE → PARTIAL (1-3 legs) → COMPLETE (all 4)
  4. If stuck at PARTIAL for > 120 seconds:
     a. Cancel all unfilled orders
     b. Close any filled legs at market
     c. strategy_status = "ENTRY_FAILED"
     d. Log the failure, alert Telegram
     e. Retry entry after cycle_delay_sec
  5. NEVER leave a partial structure active

Close Atomicity:
  1. Batch all 4 close orders
  2. If stuck: amend aggressively (walk price toward market)
  3. If still stuck after 180s: emergency market order (accept slippage)
  4. Log slippage cost

Roll Atomicity:
  1. Close old spread (2 orders) → wait for BOTH fills
  2. ONLY THEN open new spread (2 orders)
  3. If old spread close is stuck: abort roll, keep original
  4. If new spread open is stuck: cancel unfilled, close the filled one
  5. NEVER have 6 open legs simultaneously
```

**New state values:**
```python
"strategy_status": "ENTRY_PARTIAL"    # some legs filled, recovery in progress
"strategy_status": "ENTRY_FAILED"     # atomicity rollback triggered
"strategy_status": "ROLL_PARTIAL"     # mid-roll, old closed, new partially filled
```

**New leg field:**
```python
"fill_status": "pending" | "filled" | "cancelled" | "failed"
```

---

### C.2 CRITICAL: Max Loss Drift After Rolls

**The problem (already fixed in §8.2 above):** The original plan said max_loss is "fixed at entry". WRONG. After a roll that costs debit:

```
Before roll: net_credit = $45, max_loss = $1000 - $45 = $955/BTC
Roll costs $8 debit:
After roll:  effective_credit = $37, max_loss = $1000 - $37 = $963/BTC
                                                                ^^^^
                                                Max loss INCREASED by $8
```

After 3 rolls each costing $8 debit: max_loss = $955 + $24 = $979/BTC (dangerously close to wing_width).

**Guardrail:** If `effective_net_credit < 0` after a roll, the condor is **guaranteed to lose money** regardless of outcome. IC must refuse the roll and exit the cycle instead.

```python
# In ic_adjuster.py, before executing roll:
estimated_new_credit = effective_net_credit + estimated_roll_credit
if estimated_new_credit <= 0:
    log.warning("Roll would make net credit negative — exiting cycle instead")
    return EXIT_CYCLE  # Don't roll — close and start fresh
```

---

### C.3 IMPORTANT: Batch Order Integration

**Use `POST /v2/orders/batch` for all multi-leg operations:**

```python
# ic_executor.py

async def batch_place_legs(legs: list[dict]) -> dict:
    """
    Place up to 4 legs in a single API call.

    Request body:
    {
      "orders": [
        {"product_symbol": "P-BTC-82000-280326", "size": 10, "side": "sell", "order_type": "limit", "limit_price": 28.0},
        {"product_symbol": "P-BTC-81000-280326", "size": 10, "side": "buy", "order_type": "limit", "limit_price": 8.5},
        {"product_symbol": "C-BTC-88000-280326", "size": 10, "side": "sell", "order_type": "limit", "limit_price": 30.0},
        {"product_symbol": "C-BTC-89000-280326", "size": 10, "side": "buy", "order_type": "limit", "limit_price": 12.5},
      ]
    }

    Returns: list of order_ids, one per leg
    """
```

**Benefits:**
- 1 HTTP call instead of 4 (lower latency)
- All legs dispatched within same matching engine cycle
- Rate limit: 4/500 ops per second (trivial)

**Fallback:** If batch endpoint fails (e.g., network error), fall back to sequential placement with atomicity rollback from §C.1.

---

### C.4 IMPORTANT: Greeks Monitoring

Since Delta Exchange provides real-time Greeks, we should track and display them. This is free data that gives massive operational insight.

**Portfolio Greeks (computed every heartbeat):**

```python
def compute_portfolio_greeks(legs: dict, lots: int) -> dict:
    """
    Sum Greeks across all 4 legs, accounting for long/short signs.

    For sell legs: negate the Greek (selling a +0.16 delta call = -0.16 portfolio delta)
    For buy legs: keep the Greek as-is
    """
    portfolio = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
    for leg_key, leg in legs.items():
        sign = -1 if leg["action"] == "sell" else +1
        for greek in ["delta", "gamma", "theta", "vega"]:
            portfolio[greek] += sign * leg.get(f"mark_{greek}", 0) * lots
    return portfolio
```

**What this tells us:**
| Greek | Meaning for IC | Alert threshold |
|-------|----------------|-----------------|
| Delta | How much P&L changes per $1 BTC move | |delta| > 0.05 = condor is skewed |
| Gamma | Rate of delta change (danger near short strikes) | gamma > threshold = gamma risk |
| Theta | Daily time-decay income | Negative = something wrong |
| Vega | IV sensitivity | High vega exposure pre-FOMC = risk |

**Add to leg state:**
```python
"mark_delta": -0.16,    # Updated every heartbeat
"mark_gamma": -0.002,
"mark_theta": 1.50,     # Positive = earning theta
"mark_vega": -0.05,
```

**Add to cycle state:**
```python
"portfolio_greeks": {
  "delta": -0.02,        # Near-zero = balanced condor
  "gamma": -0.008,
  "theta": 5.20,         # Earning $5.20/day theta
  "vega": -0.15,
}
```

**WebUI:** Display in ICStatusBanner as small badges:
```
Δ -0.02  |  Γ -0.01  |  Θ +$5.20/d  |  V -0.15
```

---

### C.5 IMPORTANT: Expiry Handler

**The problem:** What happens if the session is running and the options expire? The heartbeat must detect and handle this gracefully.

**In ic_monitor.py heartbeat, add PHASE 2.5:**

```
PHASE 2.5: Expiry check
  if current_time >= expiry_time:
    → Mark all legs as "expired"
    → Compute settlement P&L:
      For each leg:
        if option is OTM at expiry: settlement_price = 0
        if option is ITM: settlement_price = |spot - strike|
      → settlement P&L per leg follows same formula as §8.5
    → Move cycle to history with exit_reason = "expired"
    → If auto_cycle: schedule new cycle with next expiry
```

**Important:** Delta Exchange settles BTC options in BTC, cash-settled at the DERIBIT index price at 12:00 UTC (or IST equivalent). The settlement price is known — we compute P&L using it.

**Edge case:** If IC has a leg that expires ITM but the loss is within the wings (expected for an IC), the long wing offsets the short leg's loss. The settlement P&L should match our unrealized P&L at expiry.

---

### C.6 IMPORTANT: Min Net Credit Threshold

**The problem:** If IV is low or wings are wide, the net credit could be negligible or even negative. Entering an IC with $2/BTC credit and $1000 wing width has a 500:1 risk:reward — terrible.

**Add parameter:**
```python
"min_net_credit_per_btc": 10.0,    # Reject entry if net credit < $10/BTC
```

**In ic_strike_selector.py:**
```python
if estimated_net_credit < params["min_net_credit_per_btc"]:
    log.warning(f"Net credit {estimated_net_credit} < minimum {params['min_net_credit_per_btc']} — skipping entry")
    return None  # Entry rejected; retry at next heartbeat
```

**Also add to params:**
```python
"min_credit_to_wing_ratio": 0.05,  # Net credit must be ≥ 5% of wing width
```
This prevents absurd risk:reward ratios regardless of absolute dollar amounts.

---

### C.7 IMPORTANT: Roll Guard Near Expiry

**The problem:** Rolling with DTE < 2 puts us into extreme gamma territory. The new short legs have near-expiry gamma spikes that make the condor extremely sensitive to small price moves.

**Rule:**
```python
# In ic_adjuster.py, before executing roll:
if minutes_to_expiry < (params["close_at_dte"] + 1) * 1440:
    log.info("DTE too low for roll — closing cycle instead")
    return EXIT_CYCLE  # Don't roll into gamma death zone
```

---

### C.8 IMPORTANT: Backend Restart Recovery

**Mechanism (mirrors MMM pattern):**

```python
# In ic_api.py, on blueprint registration:

def restore_running_sessions():
    """Called once at backend startup. Restores monitors for RUNNING/PAUSED sessions."""
    storage = get_storage()
    for session_id, session in storage.load_all().items():
        if session.get("status") in ("RUNNING", "PAUSED"):
            monitor = ICMonitor(session_id, session)
            monitor.start()  # Respects PAUSED status internally
            _monitors[session_id] = monitor
            log.info(f"[{session_id}] Restored after restart (status={session['status']})")

# Called from app.py after blueprint registration
```

**State persistence frequency:**
- Save to `ic_sessions.json` after EVERY heartbeat (same as MMM)
- Use file-lock pattern from `mmm_storage.py`
- On crash recovery: pick up from last saved heartbeat state

---

### C.9 IMPORTANT: Simulate Mode (Phase 1)

**Purpose:** Run the full heartbeat loop without placing real orders. Logs every decision.

**Parameter:**
```python
"simulate": True,    # Default True in development, False in production
```

**In ic_executor.py:**
```python
async def place_order(self, product_symbol, side, size, limit_price, session):
    if session.get("params", {}).get("simulate", False):
        log.info(f"[SIMULATE] Would place {side} {size} lots of {product_symbol} at {limit_price}")
        return {
            "order_id": f"SIM_{uuid.uuid4().hex[:8]}",
            "fill_price": limit_price,
            "simulated": True,
        }
    # ... real order placement
```

**Benefits:** Phase 1 can be fully tested with real market data but no real money at risk.

---

### C.10 MODERATE: Vol Skew Awareness

**Expected behavior, not a bug:** Crypto vol surface is put-skewed. At equal 0.16 delta:
- Short put at $82,000 might have $28 premium
- Short call at $89,000 might have $20 premium

This means the condor is naturally asymmetric in strike distance:
- Put short: 3.5% OTM
- Call short: 4.7% OTM

**This is fine and desirable.** The skew means puts are "more expensive" because downside risk is higher — the market prices this correctly. Our condor collects appropriate premium for the actual risk.

**UI note:** Display actual distance % for each side in ICStrikeMap so operator sees the asymmetry.

---

### C.11 MODERATE: Dynamic Strike Grid

Per operator answer, strike intervals vary ($500 near ATM, $1000+ far OTM). The strike selector must query available strikes dynamically.

**In ic_strike_selector.py:**
```python
async def get_available_strikes(symbol, expiry, option_type):
    """
    Fetch actual available strikes from Delta Exchange products API.
    Returns sorted list of strike prices.
    """
    # GET /products?contract_types=call_options&underlying_asset_symbol=BTC
    # Filter by expiry date
    # Return list of strike floats
```

**Do NOT assume $500 intervals.** Use the actual available strikes from the API.

---

### C.12 MODERATE: Activity Log Isolation

IC and MMM can share the same activity logging system, but entries must be tagged.

**Add `algo` field to activity events:**
```python
log_activity(
    activity_type="cycle_opened",
    message="IC Cycle 3 opened — net credit $45.20/BTC",
    session_id="ic_20260324_001",
    severity="info",
    details={...},
    algo="ic",        # NEW: "ic" | "mmm" | "patience" etc.
)
```

If `mmm_activity.py` doesn't support this field, create a separate `ic_activity.py` that wraps it.

---

## Appendix D — Frontend Integration Points

From architecture review of existing app.py and App.js:

### D.1 Backend Blueprint Registration

In `webui/backend/app.py`, add alongside other algo blueprints (~line 570):

```python
try:
    from webui.backend.routes.ic.ic_api import ic_bp
    app.register_blueprint(ic_bp)
    log.info("Registered IC (Iron Condor) blueprint")
except Exception as e:
    log.warning(f"IC blueprint registration failed: {e}")
```

### D.2 Frontend Route

In `webui/frontend/src/App.js`, add lazy import and route:

```javascript
const ICPage = React.lazy(() => import('./pages/ICPage'));

// In <Routes>:
<Route path="/ic" element={<ICPage socket={socket} />} />
```

### D.3 Navigation Entry

In `webui/frontend/src/config/navigationSections.js`, add to "Algorithms" group:

```javascript
{
  id: 'ic',
  label: 'Iron Condor',
  icon: ShieldIcon,              // lucide-react — represents defined-risk protection
  description: 'Defined-risk continuous iron condor strategy',
  group: 'Algorithms',
}
```

### D.4 Context Provider Pattern

Follow exact pattern from `MMMContext.js`:
- `useReducer` with actions enum
- `localStorage` for `ic_selectedSessionId`
- Polling via `useVisibilityAwarePolling`
- WebSocket subscription for `ic_*` events

### D.5 Service Layer

Follow `mmmService.js` pattern:
- Object-based (not class)
- `apiShim` for HTTP (imported from utils)
- `BASE_URL = '/api/ic'`
- Async/await for all methods

---

## Appendix E — Risk/Reward Reality Check

**For a typical BTC weekly Iron Condor:**

```
BTC spot:         $85,000
Short Put (SP):   $82,000  (premium $28)
Long Put (LP):    $81,000  (premium $8)
Short Call (SC):  $88,000  (premium $30)
Long Call (LC):   $89,000  (premium $12)

Net credit:       $28 + $30 - $8 - $12 = $38/BTC
Wing width:       $1,000
Max loss:         $1,000 - $38 = $962/BTC
Risk:reward:      $962 : $38 = 25.3 : 1

For 10 lots (0.01 BTC):
  Max profit:     $0.38
  Max loss:       $9.62
```

**This is a high-probability, low-payout strategy.** The operator should understand:
- Win rate is ~70-80% (probability of staying between short strikes)
- BUT each loss wipes ~25 winning cycles
- Adjustments (rolling) are what turns this from net-negative to net-positive over time
- The algo MUST be disciplined about exit timing and adjustment quality

**Add to WebUI:** Show risk:reward ratio prominently in Create Session dialog so the operator understands what they're getting into.

---

*End of Iron Condor Implementation Plan (Revised)*
*Phase 1+2+3 complete (2026-03-24). Next step: Phase 4 (WebUI) → Phase 5 (Testing & Hardening)*

---

## Appendix F — Known Simulation Mode Runtime Errors

**Bug 1: 405 Method Not Allowed on Session Endpoints**
- **Symptom:** Operations like `DELETE /api/ic/sessions/<id>` and `POST /api/ic/sessions/<id>/stop` fail with HTTP 500 (Internal Server Error) logging a `405 Method Not Allowed` Werkzeug routing exception in the backend logs (`webui_production_error.log`).
- **Root Cause:** There is an endpoint mismatch in `ic_api.py`. The session control routes (delete, start, stop, pause, resume) are registered with the singular path `@ic_bp.route('/session/<session_id>...')` (e.g. line 164), but the UI/scripts query the plural path `/sessions/`.
- **Action Required:** Update `ic_api.py` to change `/session/` to `/sessions/` across all 5 session control endpoints.
