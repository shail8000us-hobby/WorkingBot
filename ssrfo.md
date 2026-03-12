# SSRFO — Futures Grid + Options Premium Algo

> **Version**: 1.1 (Planning — Reviewed & Fixed)  
> **Date**: February 21, 2026 (updated March 11, 2026)  
> **Status**: PLAN — Not yet implemented  
> **Author**: SSR + AI  
> **Currency**: All premium/P&L values are in **INR** (Delta Exchange India settles in INR)  
> **Options Style**: European (exercisable only at expiry — no early assignment risk)  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategy Walkthrough — From Notes](#2-strategy-walkthrough--from-notes)
3. [Strategy Enhancement — Institutional Grade](#3-strategy-enhancement--institutional-grade)
4. [Architecture & Technical Design](#4-architecture--technical-design)
5. [File Structure & Module Design](#5-file-structure--module-design)
6. [State Machine & Data Models](#6-state-machine--data-models)
7. [Core Engine Logic — Step by Step](#7-core-engine-logic--step-by-step)
8. [EventStore Poller Design](#8-eventstore-poller-design)
9. [Options Order Logic](#9-options-order-logic)
10. [MMM Bridge — Auto-Spawning Sessions](#10-mmm-bridge--auto-spawning-sessions)
11. [Expiry Watcher — Edge Cases](#11-expiry-watcher--edge-cases)
12. [Safety & Risk Management](#12-safety--risk-management)
13. [REST API Design](#13-rest-api-design)
14. [WebSocket Events](#14-websocket-events)
15. [Frontend Dashboard](#15-frontend-dashboard)
16. [Configuration Parameters](#16-configuration-parameters)
17. [Integration with Existing Systems](#17-integration-with-existing-systems)
18. [Testing Plan](#18-testing-plan)
19. [Implementation Phases](#19-implementation-phases)
20. [Open Questions & Stuck Points](#20-open-questions--stuck-points)
21. [Risk Register](#21-risk-register)

---

## 1. Executive Summary

### What is SSRFO?

**SSRFO** (SSR Futures + Options) is a dual-income trading algorithm that enhances the existing BTC grid bot by automatically selling BTC call options (CE) on every grid entry. It creates a **synthetic covered call** on each grid level — collecting both grid trading profits AND options theta premium on every trade.

### The Big Idea

```
Per lot (0.001 BTC, grid step = 500):
  Grid profit per lot   = 500 × 0.001 = ₹0.50
  CE premium per lot    = ~₹3-5 (varies with IV and time to expiry)

With lot_size = 5:
  Grid Bot alone:         BUY 5 lots @ 60000 → SELL @ 60500 = ₹2.50 profit
  Grid Bot + SSRFO:       BUY 5 lots @ 60000 → SELL 5 CE @ 60500 = ~₹20 premium
                          → SELL @ 60500 = ₹2.50 + ₹20 = ₹22.50 total (~9x more)
                          → If CE expires worthless = ₹2.50 + ₹20 premium kept

Note: Premium income dominates grid P&L. The multiplier depends heavily on
      IV (implied volatility) and time to expiry at the moment of CE sell.
```

### Income Streams

| Stream | Source | When |
|--------|--------|------|
| **Grid P&L** | Future TP fills (entry + step) | Every grid cycle |
| **CE Premium** | Time decay of sold CEs | Continuous (theta) |
| **MMM P&L** | Orphaned CE+PE strangle managed by MMM | When CE is separated from future |

### Architecture Decision

SSRFO runs as a **WebUI backend module** (like MMM and SSR Algo), registered as a Flask Blueprint at `/api/ssrfo`. It polls the grid bot's EventStore SQLite database for fill events, then places options orders through the existing options infrastructure.

### Scope (v1)

- **LONG mode only** (BUY futures on dips, SELL CE for premium)
- **BTC only** (BTCUSD perpetual futures + BTC options on Delta Exchange India)
- **1:1 lot ratio** (1 future lot = 1 CE lot) — **MUST VERIFY** that BTC options contract multiplier matches futures (0.001 BTC). See §20 Q1/Q2.
- **European-style options** — no early assignment risk (can only be exercised at expiry)
- **Auto MMM handoff** for orphaned options
- **INR-settled** — all premium, P&L, and margin values in Indian Rupees

---

## 2. Strategy Walkthrough — From Notes

This section is a precise transcription and formalization of the handwritten notes.

### 2.1 Basic Flow — Market Going Down (Grid Entries)

**Setup:** BTC grid bot running in LONG mode. Market at 60,500. Grid step = 500.

#### Trade 1: Market drops to 60,000

```
┌─────────────────────────────────────────────────────────────────────┐
│ GRID BOT:  BUY 1 lot BTC Future @ 60,000                          │
│            TP order placed at 60,500 (entry + step)                │
│                                                                     │
│ SSRFO:     On fill confirmation from exchange...                   │
│            SELL 1 lot CE at nearest strike to 60,500 (±100)        │
│            Expiry: nearest available with ≥24 hours remaining      │
└─────────────────────────────────────────────────────────────────────┘
```

**Positions after Trade 1:**

| Instrument | Position | Details |
|-----------|----------|---------|
| BTC Future | +1 lot @ 60,000 | TP order at 60,500 |
| BTC Option | -1 CE @ strike 60,500 (±100) | Expiry ≥ 24h |

#### Trade 2: Market drops further to 59,500

```
┌─────────────────────────────────────────────────────────────────────┐
│ GRID BOT:  BUY 1 lot BTC Future @ 59,500                          │
│            TP order placed at 60,000 (entry + step)                │
│                                                                     │
│ SSRFO:     On fill confirmation from exchange...                   │
│            SELL 1 lot CE at nearest strike to 60,000 (±100)        │
│            Same expiry rules apply                                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Positions after Trade 2:**

| Instrument | Position | Details |
|-----------|----------|---------|
| BTC Future | +1 lot @ 60,000 | TP → 60,500 |
| BTC Future | +1 lot @ 59,500 | TP → 60,000 |
| BTC CE | -1 lot @ strike ~60,500 | Expiry ≥ 24h |
| BTC CE | -1 lot @ strike ~60,000 | Expiry ≥ 24h |
| **Open TP Orders** | SELL @ 60,500 (1 lot), SELL @ 60,000 (1 lot) | |

This process continues as market trends down, up to the defined grid limits.

### 2.2 Behavior on Up Move — TP Fills

**Starting positions (from above):**

| Instrument | Position |
|-----------|----------|
| BTC Future | +1 lot @ 60,000 (TP 60,500) |
| BTC Future | +1 lot @ 59,500 (TP 60,000) |
| BTC CE | -1 lot @ strike ~60,500 (±100) |
| BTC CE | -1 lot @ strike ~60,000 (±100) |

#### Event: Market rises to 60,000 → TP order fills

```
┌─────────────────────────────────────────────────────────────────────────┐
│ GRID BOT:  TP filled — Future bought @ 59,500 sold @ 60,000           │
│            Profit = 500 × 0.001 × 1 = ₹0.50 (per lot)                 │
│            With lot_size=5: ₹2.50 profit                               │
│                                                                         │
│ REMAINING: +1 lot Future @ 60,000 (TP 60,500)                         │
│            -1 CE @ ~60,500                                             │
│            -1 CE @ ~60,000  ← THIS CE IS NOW ORPHANED                 │
│                                                                         │
│ SSRFO:     Detects TP fill → The CE @ 60,000 no longer has a paired   │
│            future position to cover it.                                 │
│                                                                         │
│ ACTION:    SELL -1 PE at strike ~59,500 (±100) of SAME expiry          │
│            → Creates a CE+PE strangle for MMM to manage                │
│            → Spawn MMM session: "mmm-ssrfo-59500-1"                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**MMM takes over:** The strangle (-1 CE @ 60,000, -1 PE @ 59,500) is now managed by MMM algo autonomously — shifting, adjusting, close-at-5, wind-down, all the existing MMM capabilities.

#### Event: Market continues to 60,500 → Second TP fills

```
┌─────────────────────────────────────────────────────────────────────────┐
│ GRID BOT:  TP filled — Future bought @ 60,000 sold @ 60,500           │
│            Profit = 500 × 0.001 × 1 = ₹0.50 per lot                   │
│                                                                         │
│ REMAINING: BTC Future = 0 positions                                    │
│            -1 CE @ ~60,500  ← THIS CE IS NOW ORPHANED                 │
│                                                                         │
│ SSRFO:     Detects TP fill → CE @ 60,500 orphaned                     │
│                                                                         │
│ ACTION:    SELL -1 PE at strike ~60,000 (±100) of same expiry          │
│            → Spawn MMM session: "mmm-ssrfo-60000-1"                    │
│            → MMM manages the -1 CE @ 60,500 + -1 PE @ 60,000          │
└─────────────────────────────────────────────────────────────────────────┘
```

**This process repeats continuously as market moves up and down.**

### 2.3 Expiry Edge Case — CE Expires While Future Exists

**Scenario:** BTC Future bought at 60,000 with TP at 60,500. CE sold at strike ~60,500 with expiry ≥ 24 hours. **After 24+ hours, the CE expires but the future position still exists.**

The CE at 60,500 strike expires worthless (assuming market is not at/above 60,500), but the future at 60,000 is still there. **We need to decide what to do with the naked future.**

**Decision tree (evaluated in this order, first match wins):**

| Priority | Case | Condition | Example (entry=60,000) |
|----------|------|-----------|------------------------|
| 1st | Case 1 | market > entry × 1.005 | market > 60,300 |
| 2nd | Case 3 | market < entry - grid_step | market < 59,500 |
| 3rd | Case 2 | market < entry - reentry_pts | market < 59,800 |
| 4th | Case 4 | everything else (near entry) | 59,800 ≤ market ≤ 60,300 |

**Check market price relative to entry (60,000):**

#### Case 1: Market > entry + 0.5% (e.g., > 60,300)

```
Market is ABOVE entry — the future is in profit territory.
ACTION: Close the 60,000 BTC future at market price.
        Cancel the TP order at 60,500.
        Book the profit.
RATIONALE: CE expired, no more premium hedge. Take profit and exit cleanly.
```

#### Case 3: Market < entry - grid_step (e.g., < 59,500)

```
Market is DEEPLY below entry — the future is significantly underwater.
ACTION: Sell new CE at strike ~60,000 (ENTRY level, not TP level).
        Closer to ATM = higher premium.
        Resume SSRFO tracking.
RATIONALE: The market is very weak. Sell closer-to-ATM CE for higher premium.
           Accept that if market rallies past 60,000, the CE might go ITM.
```

#### Case 2: Market < entry - reentry_pts (e.g., < 59,800)

```
Market is moderately below entry — the future is underwater but not deeply.
ACTION: Sell new CE at strike ~60,500 (TP level) with fresh ≥24h expiry.
        Resume normal SSRFO tracking as before.
RATIONALE: Re-establish the covered call. Collect more premium while
           waiting for TP to fill. Grid logic will handle the future.
```

#### Case 4: Market between entry - reentry_pts and entry + 0.5% (e.g., 59,800 to 60,300)

```
Market is NEAR entry — ambiguous zone.
ACTION: Evaluate if CE premium is attractive at TP strike.
        If premium > minimum_threshold → Sell CE at TP strike, resume tracking.
        If premium too low → Close future at market, take small loss/gain.
RATIONALE: Premium must justify the margin. If premium is thin,
           better to cut the position cleanly.
```

### 2.4 MMM Session Naming Convention

When SSRFO spawns MMM sessions for orphaned options, they are named:

```
mmm-ssrfo-{entry_price}-{sequence}

Examples:
  mmm-ssrfo-59500-1    (1st session for orphan from 59500 entry)
  mmm-ssrfo-60000-1    (1st session for orphan from 60000 entry)
  mmm-ssrfo-59500-2    (2nd session if another orphan at 59500)
```

The MMM session manages the CE+PE strangle independently. SSRFO tracks the session ID for monitoring but does not interfere with MMM's internal decisions.

---

## 3. Strategy Enhancement — Institutional Grade

Beyond the handwritten notes, these enhancements elevate SSRFO to institutional quality.

### 3.1 Premium Threshold Gate

**Problem:** If IV is very low, the CE premium might be negligible (e.g., ₹0.50). Selling for tiny premium wastes margin and creates risk for no return.

**Solution:** Before selling CE, check if premium ≥ `min_ce_premium` (configurable, default ₹3). If premium is too low:
- Log the skip with reason
- Set pair status to `CE_SKIPPED_LOW_PREMIUM`
- The future runs without an options hedge for this cycle
- Re-evaluate on next expiry check cycle

### 3.2 Net Delta Tracking

Track the combined delta of all futures + options positions:

```
Net Delta = Σ(future_lots × 1.0) + Σ(CE_short_lots × (-delta_CE))
```

Display on dashboard. Alert if net delta exceeds configurable threshold (e.g., > 80% or < -10%). This shows the actual directional exposure vs the hedged exposure.

### 3.3 Premium P&L Attribution

Track premium decay separately from grid P&L:

| Metric | Calculation |
|--------|-------------|
| Grid P&L | `Σ(TP fills × step × contract_multiplier × lots)` |
| Premium Collected | `Σ(CE sell premium × lots)` at entry |
| Premium Remaining | `Σ(current CE mark_price × lots)` for active CEs |
| Premium P&L | `Premium Collected - Premium Remaining - Σ(CE buyback costs)` |
| MMM Session P&L | Sum of P&L from all spawned MMM sessions |
| **Total SSRFO P&L** | Grid P&L + Premium P&L + MMM Session P&L |

### 3.4 Volatility-Aware Strike Selection

Instead of blind ±100 tolerance:
- **High IV (>80%):** Sell CE further OTM (strike = TP + 200) for safety
- **Normal IV (40-80%):** Standard ±100 tolerance
- **Low IV (<40%):** Sell closer to ATM (strike = TP - 100) for better premium, OR skip if premium still too low

### 3.5 Margin Efficiency Monitor

Before every CE sell, verify:
```
available_margin > required_margin_for_CE × safety_factor(1.5)
```

If margin is insufficient:
- Queue the CE sell for retry when margin frees up
- Alert via Telegram
- Never skip silently — track as `CE_PENDING_MARGIN`

### 3.6 Position Reconciliation

Every 5 minutes, reconcile SSRFO's internal state against exchange positions:
- Fetch `GET /v2/positions` from exchange
- Compare tracked pairs vs actual positions
- Flag discrepancies: phantom pairs (SSRFO thinks it exists but exchange doesn't), orphans (exchange has it but SSRFO doesn't track it)
- Auto-correct or alert based on severity

### 3.7 Graceful Degradation

```
If grid bot stops → SSRFO pauses new CE sells.
                   → For existing ACTIVE pairs: CE is still short, future TP is likely cancelled.
                   → SSRFO must either:
                       a) Sell PE to form strangle + hand to MMM (if CE has significant premium remaining)
                       b) Buy back CE at market (if CE premium is low enough for profitable close)
                       c) Hold CE and wait for grid bot restart (if max_naked_hours not exceeded)
                   → Track gridbot heartbeat via EventStore last-write timestamp.
                   → Alert if gridbot silent > 5 minutes.

If MMM module fails → SSRFO manages orphaned options directly (basic mode: close at 5₹)
If options chain unavailable → Skip CE sells, log, retry on next fill
If exchange API rate-limited → Exponential backoff with shared rate limiter queue
```

### 3.8 CE ITM Buyback Protection

**Problem:** If BTC rallies hard after a CE is sold, the CE goes ITM and its loss can exceed the grid profit + premium collected. The document has no exit mechanism for this scenario.

**Solution:** Monitor all ACTIVE pairs every heartbeat:

```
For each ACTIVE pair:
  ce_mark = current mark price of the CE
  ce_sold = pair.ce_premium (entry price)
  ce_delta = CE delta from chain service

  Trigger buyback if ANY of:
    1. ce_mark > ce_sold × 3.0   (CE tripled — loss exceeding premium)
    2. ce_delta > 0.70            (CE is deep ITM, high assignment-equivalent risk)
    3. ce_mark > max_ce_loss      (configurable hard stop per CE position)

  On buyback trigger:
    → Buy back CE at market (place_smart_order side='buy', reduce_only=True)
    → Update pair status to CLOSED
    → Log buyback reason, mark-to-market loss
    → Alert Telegram: "🔴 CE buyback triggered"
```

### 3.9 PE Premium Threshold Gate

**Problem:** When selling PE to form a strangle after TP fill, no premium check is performed. Could sell PE for negligible premium, wasting margin.

**Solution:** Before selling PE in `process_tp_fill()`, verify:
```
pe_premium >= session.params['min_pe_premium']  (default ₹3)
```

If PE premium is too low:
- Log the skip with reason
- Leave pair as `TP_FILLED` (CE orphaned but no strangle)
- Alert: "PE premium too low for strangle, CE orphan unmanaged"
- The orphaned CE will be managed by expiry watcher or manual intervention

### 3.10 Per-Strike Position Limit

**Problem:** Multiple grid entries with similar TP prices could result in SSRFO selling many CE lots at the exact same strike, concentrating risk.

**Solution:** Track total short lots per CE strike across all active pairs:
```
For CE strike selection:
  existing_lots_at_strike = count lots already short at candidate strike
  max_lots_per_strike = session.params['max_lots_per_strike']  (default: lot_size × 3)

  If existing_lots_at_strike + new_lots > max_lots_per_strike:
    → Log: "Strike {strike} at capacity ({existing}/{max})"
    → Try next available strike within tolerance
    → If no alternative: create pair as NAKED_FUTURE with reason
```

### 3.11 Shared Rate Limiter

**Problem:** Delta Exchange allows ~10 req/s. SSRFO, MMM, SSR Algo, and Options module all share the same API. No coordination exists.

**Solution:** Implement a cross-module token-bucket rate limiter:
```python
# Shared via Flask app.config['RATE_LIMITER']
# All modules call: rate_limiter.acquire() before exchange API calls
# Token bucket: 8 tokens/sec (leaves 2/s headroom), burst=15
# If bucket empty: queue with timeout, log warning
```

This is stored in `webui/backend/shared/rate_limiter.py` and imported by all modules.

### 3.12 Transaction Cost Modeling

**Problem:** If the CE bid-ask spread is wide (e.g., bid=₹3, ask=₹5), the effective premium received after selling could be much lower than the mark price suggests.

**Solution:** Before CE sell, evaluate transaction cost:
```
spread = ask - bid
spread_pct = spread / mid_price × 100

Skip CE sell if:
  spread_pct > 20%  (spread too wide, poor execution likely)
  OR bid_size < lot_size  (insufficient liquidity at bid)

Use spread-adjusted premium for threshold check:
  effective_premium = bid_price (worst case), not mark_price
```

### 3.13 Kill Switch — Emergency Close All

**Design:** One-click endpoint that:
1. Buys back ALL short CEs across all pairs (market orders)
2. Does NOT close futures (grid bot manages those)
3. Stops all MMM sessions spawned by SSRFO
4. Sets session status to STOPPED
5. Cancels any pending CE/PE orders
6. Sends Telegram critical alert

```
POST /api/ssrfo/session/<id>/kill
```

---

## 4. Architecture & Technical Design

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DELTA EXCHANGE INDIA                                │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────────┐    │
│  │ BTC Perpetual │  │ BTC Call Options  │  │ BTC Put Options            │    │
│  │ (Futures)     │  │ (CE at strike X)  │  │ (PE at strike Y)           │    │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬─────────────────┘    │
│         │                   │                       │                       │
└─────────┼───────────────────┼───────────────────────┼───────────────────────┘
          │                   │                       │
          │ WebSocket fills   │ REST API orders       │ REST API orders
          ▼                   │                       │
┌──────────────────┐          │                       │
│ GRID BOT         │          │                       │
│ (PM2 process)    │          │                       │
│                  │          │                       │
│ EventStore ──────┼──(SQLite DB)──┐                  │
│ bot_events_      │          │    │                  │
│ BTCUSD_LONG.db   │          │    │                  │
└──────────────────┘          │    │ Poll (1s)        │
                              │    ▼                  │
                    ┌─────────┴────────────────────────┴──────────────────┐
                    │ WEBUI BACKEND (Flask, PM2 process: webui-backend)   │
                    │                                                     │
                    │  ┌──────────────────────────────────────────────┐   │
                    │  │ SSRFO MODULE (Blueprint: /api/ssrfo)        │   │
                    │  │                                              │   │
                    │  │  ┌─────────────┐    ┌──────────────────┐    │   │
                    │  │  │ EventStore  │    │ Options Order    │    │   │
                    │  │  │ Poller      │───▶│ Engine           │    │   │
                    │  │  │ (1s loop)   │    │ (CE sell logic)  │    │   │
                    │  │  └─────────────┘    └──────┬───────────┘    │   │
                    │  │                            │                │   │
                    │  │  ┌─────────────┐    ┌──────▼───────────┐    │   │
                    │  │  │ Expiry      │    │ MMM Bridge       │    │   │
                    │  │  │ Watcher     │    │ (session spawner)│    │   │
                    │  │  │ (60s loop)  │    └──────┬───────────┘    │   │
                    │  │  └─────────────┘           │                │   │
                    │  │                            │                │   │
                    │  │  ┌──────────────────┐      │                │   │
                    │  │  │ State & Storage  │      │                │   │
                    │  │  │ (SQLite WAL)     │      │                │   │
                    │  │  └──────────────────┘      │                │   │
                    │  └────────────────────────────┼────────────────┘   │
                    │                               │                    │
                    │  ┌────────────────────────────▼────────────────┐   │
                    │  │ MMM MODULE (existing)                       │   │
                    │  │  Manages orphaned CE+PE strangles           │   │
                    │  │  - Shifting, adjustment, close-at-5         │   │
                    │  │  - Wind-down, reversal handling             │   │
                    │  └────────────────────────────────────────────┘   │
                    │                                                     │
                    │  ┌────────────────────────────────────────────┐    │
                    │  │ OPTIONS INFRA (existing)                    │    │
                    │  │  - OptionsChainService (chain data)         │    │
                    │  │  - place_smart_order() (order execution)    │    │
                    │  │  - UnifiedAPIClient (exchange comms)        │    │
                    │  └────────────────────────────────────────────┘    │
                    └─────────────────────────────────────────────────────┘
```

### 4.2 Process Boundary

```
PM2 Process: gridbot-btc-live
  └── async_gridbot.py → writes to EventStore SQLite (WAL mode)

PM2 Process: webui-backend (port 5555)
  └── app.py
      ├── MMM module (existing) — manages options strangles
      ├── SSR Algo module (existing) — butterfly adjustments
      ├── Options module (existing) — chain data + order placement
      └── SSRFO module (NEW) — bridges gridbot to options
          ├── Reads EventStore SQLite (read-only, WAL concurrent reader)
          ├── Places options orders via existing options infra
          └── Creates MMM sessions via internal function calls
```

**Key:** SSRFO and MMM are in the **same Flask process**, so SSRFO can call MMM functions directly — no HTTP overhead, no network failure mode.

### 4.3 Data Flow

```
1. Grid Bot fills BUY order on exchange
2. Exchange sends fill via WebSocket → Grid Bot processes it
3. Grid Bot writes POSITION_OPENED event to EventStore SQLite DB
4. SSRFO poller (1s interval) reads new event from SQLite
5. SSRFO engine determines: entry fill → need to sell CE
6. SSRFO options module:
   a. Fetches chain data from OptionsChainService
   b. Selects strike (nearest to TP within ±tolerance)
   c. Selects expiry (nearest with ≥24h remaining)
   d. Places CE sell order via place_smart_order()
7. SSRFO creates FutureOptionPair record, persists to SSRFO SQLite DB
8. SSRFO emits SocketIO event + Telegram alert

Later, when grid bot fills SELL (TP):
9.  Grid Bot writes POSITION_CLOSED event to EventStore
10. SSRFO poller reads POSITION_CLOSED event
11. SSRFO engine determines: TP fill → CE is now orphaned
12. SSRFO options module: Sells PE at entry_price strike (same expiry)
13. SSRFO MMM bridge: Creates MMM session via internal API
14. MMM module takes over strangle management autonomously
```

---

## 5. File Structure & Module Design

### 5.1 Directory Layout

```
webui/backend/routes/ssrfo/
├── __init__.py                 # Exports: ssrfo_bp, init_ssrfo, init_websocket
├── ssrfo_api.py                # Flask Blueprint, REST endpoints (/api/ssrfo/*)
├── ssrfo_engine.py             # Core decision logic + safety checks + expiry watcher
├── ssrfo_monitor.py            # Background polling (eventlet) for EventStore
├── ssrfo_options.py            # Strike selection, expiry selection, CE/PE selling
├── ssrfo_state.py              # Dict-based models, enums, config defaults + validation
├── ssrfo_storage.py            # SQLite persistence (data/ssrfo_sessions.db)
├── ssrfo_mmm_bridge.py         # MMM session creation/tracking
├── ssrfo_notifications.py      # SocketIO + Telegram notifications combined
└── tests/
    ├── test_ssrfo_engine.py
    ├── test_ssrfo_options.py
    ├── test_ssrfo_expiry.py
    └── test_ssrfo_state.py
```

### 5.2 Module Responsibilities

| Module | Lines (est.) | Responsibility | Dependencies |
|--------|-------------|----------------|--------------|
| `ssrfo_api.py` | ~600 | REST routes, request validation, session CRUD, kill switch | All modules |
| `ssrfo_engine.py` | ~800 | Fill handling, expiry cases, safety checks, circuit breakers, CE ITM buyback, reconciliation | options, mmm_bridge, state |
| `ssrfo_monitor.py` | ~400 | eventlet green thread, EventStore polling, fill routing | engine, storage, EventStore DB |
| `ssrfo_options.py` | ~450 | Strike/expiry selection, order placement, premium checks, spread checks | OptionsChainService, place_smart_order |
| `ssrfo_state.py` | ~350 | Dict factories, enums, config defaults, param validation, schema migrations | None (pure data) |
| `ssrfo_storage.py` | ~350 | SQLite CRUD, WAL mode, migration support, schema versioning | sqlite3 |
| `ssrfo_mmm_bridge.py` | ~300 | MMM session creation via 2-step API, import mode, tracking, P&L aggregation | MMM module internals |
| `ssrfo_notifications.py` | ~200 | SocketIO emit wrappers + Telegram message formatting | flask_socketio, telegram helpers |

### 5.3 Dependency Graph

```
ssrfo_api.py
  ├── ssrfo_engine.py
  │     ├── ssrfo_options.py
  │     │     ├── OptionsChainService (existing)
  │     │     ├── place_smart_order() (existing)
  │     │     └── ssrfo_config.py
  │     ├── ssrfo_mmm_bridge.py
  │     │     └── MMM module internals (existing)
  │     ├── ssrfo_state.py
  │     └── ssrfo_safety.py
  ├── ssrfo_monitor.py
  │     ├── EventStore SQLite (gridbot, read-only)
  │     ├── ssrfo_engine.py
  │     └── ssrfo_storage.py
  ├── ssrfo_expiry_watcher.py
  │     ├── ssrfo_options.py
  │     └── ssrfo_engine.py
  ├── ssrfo_storage.py
  ├── ssrfo_websocket.py
  └── ssrfo_telegram.py
```

---

## 6. State Machine & Data Models

### 6.1 Session State Machine

```
                    ┌──────┐
            create  │ IDLE │
           ┌────────┤      │
           │        └──────┘
           │
           ▼
      ┌──────────┐     stop      ┌─────────┐
      │ RUNNING  │──────────────▶│ STOPPED  │
      │          │               │          │
      └────┬─────┘               └──────────┘
           │                          ▲
      pause│                          │stop
           ▼                          │
      ┌──────────┐     resume    ┌────┴─────┐
      │ PAUSED   │──────────────▶│ RUNNING  │
      │          │               │          │
      └────┬─────┘               └──────────┘
           │
      stop │
           ▼
      ┌──────────┐
      │ STOPPED  │
      └──────────┘
```

**States:**
- **IDLE**: Session created, config set, not active
- **RUNNING**: Polling EventStore, processing fills, selling CEs
- **PAUSED**: Temporarily suspended (manual or safety trigger), existing pairs maintained
- **STOPPED**: Session ended, no more processing (pairs may still have active options)

### 6.2 Pair State Machine

Each `FutureOptionPair` tracks one grid entry + its paired CE:

```
Grid BUY filled
      │
      ▼
┌──────────────┐    CE order placed     ┌─────────────────┐
│ PENDING_CE   │───────────────────────▶│ ACTIVE           │
│              │                         │ (Future + CE)    │
└──────────────┘                         └────┬─────┬──────┘
      │                                       │     │
      │ CE sell failed/skipped                │     │ CE expires
      ▼                                       │     ▼
┌──────────────┐                              │ ┌──────────────┐
│ NAKED_FUTURE │◀─────────────────────────────┘ │ CE_EXPIRED    │
│ (no CE hedge)│                                │ (future only) │
└──────────────┘                                └───┬──────────┘
                                                    │
                        ┌───────────────────────────┤
                        │ Case 1        │ Case 2/3  │ Case 4
                        ▼               ▼           ▼
                  ┌──────────┐   ┌──────────┐  ┌──────────┐
                  │ CLOSED   │   │ ACTIVE   │  │ CLOSED   │
                  │ (profit) │   │ (new CE) │  │ (market) │
                  └──────────┘   └──────────┘  └──────────┘

From ACTIVE:
      │
      │ Future TP fills
      ▼
┌──────────────────┐    PE sold + MMM created     ┌──────────────┐
│ TP_FILLED        │─────────────────────────────▶│ HANDED_TO_MMM│
│ (CE orphaned)    │                               │              │
└──────────────────┘                               └──────┬───────┘
                                                          │
                                                          │ MMM session ends
                                                          ▼
                                                   ┌──────────────┐
                                                   │ CLOSED       │
                                                   └──────────────┘
```

### 6.3 Data Models

#### SSRFOSession

```python
# Using dicts (not dataclasses) to match MMM's pattern — serializes naturally to JSON/SQLite.

def create_ssrfo_session(session_id: str, symbol: str, grid_step: float,
                         lot_size: int, eventstore_db_path: str,
                         params: dict = None) -> dict:
    """Create a new SSRFO session state dict."""
    from datetime import datetime, timezone
    merged_params = {**SSRFO_DEFAULT_PARAMS}
    if params:
        merged_params.update(params)
    return {
        'session_id': session_id,              # e.g., "ssrfo-btc-1"
        'status': 'IDLE',                      # IDLE, RUNNING, PAUSED, STOPPED
        'symbol': symbol,                      # "BTCUSD"
        'created_at': datetime.now(timezone.utc).isoformat(),
        'started_at': None,
        'stopped_at': None,
        # Grid bot link
        'grid_step': grid_step,                # 500 for BTC
        'lot_size': lot_size,                  # 5 for BTC
        'eventstore_db_path': eventstore_db_path,
        'last_processed_timestamp': 0.0,       # For polling cursor
        'last_processed_correlation_id': '',    # Dedup
        # Config
        'params': merged_params,
        # Tracking
        'pairs': [],                           # List of pair dicts
        'spawned_mmm_sessions': [],            # MMM session IDs
        # Stats
        'total_pairs_created': 0,
        'total_ce_sold': 0,
        'total_ce_premium_collected': 0.0,
        'total_grid_pnl': 0.0,
        'total_mmm_pnl': 0.0,
        'total_pnl': 0.0,
        # Safety
        'circuit_breaker_active': False,
        'consecutive_failures': 0,
        'last_error': None,
        'last_reconciliation': None,
        # Schema version for migrations (A3)
        '_schema_version': 1,
    }

#### FutureOptionPair

```python
def create_future_option_pair(session: dict, fill_event: dict,
                               tp_price: float, **kwargs) -> dict:
    """Create a new FutureOptionPair state dict."""
    import uuid
    from datetime import datetime, timezone
    return {
        'pair_id': str(uuid.uuid4()),
        'session_id': session['session_id'],
        'status': kwargs.get('status', 'PENDING_CE'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        # Future side
        'future_entry_price': fill_event.get('entry_price'),
        'future_tp_price': tp_price,
        'future_size': fill_event.get('size', session['lot_size']),
        'future_fill_correlation_id': fill_event.get('correlation_id'),
        'future_fill_time': fill_event.get('timestamp'),
        'future_side': 'buy',  # LONG mode only (v1)
        # CE side
        'ce_strike': kwargs.get('ce_strike'),
        'ce_symbol': kwargs.get('ce_symbol'),
        'ce_lots': kwargs.get('ce_lots'),
        'ce_premium': kwargs.get('ce_premium'),
        'ce_total_premium': None,  # computed: ce_premium × ce_lots
        'ce_order_id': kwargs.get('ce_order_id'),
        'ce_fill_time': kwargs.get('ce_fill_time'),
        'ce_expiry_time': kwargs.get('ce_expiry_time'),
        'ce_expiry_ddmmyyyy': kwargs.get('ce_expiry_ddmmyyyy'),
        # TP fill tracking
        'tp_fill_time': None,
        'tp_fill_correlation_id': None,
        'grid_pnl': None,
        # Orphan management
        'pe_strike': None,
        'pe_symbol': None,
        'pe_lots': None,
        'pe_premium': None,
        'pe_order_id': None,
        'mmm_session_id': None,
        # Expiry case tracking
        'expiry_case': None,
        'expiry_action_taken': None,
        'expiry_new_ce_symbol': None,
        # Lock for race condition prevention (S4)
        '_processing': False,
    }
```

---

## 7. Core Engine Logic — Step by Step

### 7.1 Engine: `process_entry_fill()`

Called when poller detects a POSITION_OPENED event (grid BUY filled):

```python
async def process_entry_fill(session, fill_event):
    """
    Grid bot BUY order filled. Sell CE at TP strike.
    
    Args:
        session: SSRFOSession
        fill_event: {entry_price, size, correlation_id, timestamp, ...}
    """
    
    # 1. Dedup check
    if is_already_processed(session, fill_event.correlation_id):
        return  # Already handled
    
    # 2. Calculate TP price
    tp_price = fill_event.entry_price + session.grid_step
    
    # 3. Safety checks
    safety_result = await run_safety_checks(session, fill_event)
    if not safety_result.allowed:
        create_pair_with_status(session, fill_event, "NAKED_FUTURE", 
                               reason=safety_result.reason)
        alert_telegram(f"CE sell blocked: {safety_result.reason}")
        return
    
    # 4. Select CE strike and expiry
    ce_strike, ce_symbol, ce_expiry = await select_ce_parameters(
        tp_price=tp_price,
        tolerance=session.params['strike_tolerance'],
        min_expiry_hours=session.params['min_expiry_hours']
    )
    
    # 5. Check premium threshold
    premium = await get_ce_premium(ce_symbol)
    if premium < session.params['min_ce_premium']:
        create_pair_with_status(session, fill_event, "CE_SKIPPED_LOW_PREMIUM",
                               reason=f"Premium {premium} < min {session.params['min_ce_premium']}")
        return
    
    # 6. Place CE sell order
    order_result = await place_ce_sell(
        symbol=ce_symbol,
        lots=session.lot_size,  # 1:1 ratio
        order_preference=session.params['order_preference']
    )
    
    # 7. Create pair record
    pair = create_future_option_pair(
        session=session,
        fill_event=fill_event,
        tp_price=tp_price,
        ce_strike=ce_strike,
        ce_symbol=ce_symbol,
        ce_lots=session.lot_size,
        ce_premium=order_result.fill_price,
        ce_order_id=order_result.order_id,
        ce_expiry=ce_expiry,
        status="ACTIVE"
    )
    
    # 8. Persist
    save_pair(session, pair)
    update_session_stats(session, premium_collected=order_result.fill_price * session.lot_size)
    
    # 9. Emit events
    emit_socketio('ssrfo_ce_sold', pair_to_dict(pair))
    send_telegram(f"🟢 SSRFO CE sold: {ce_symbol} @ {order_result.fill_price} "
                  f"| Future @ {fill_event.entry_price} → TP {tp_price}")
```

### 7.2 Engine: `process_tp_fill()`

Called when poller detects a POSITION_CLOSED event (grid SELL/TP filled):

```python
async def process_tp_fill(session, fill_event):
    """
    Grid bot TP order filled. CE is now orphaned.
    Sell PE to form strangle, hand off to MMM.
    
    Args:
        session: dict (SSRFOSession)
        fill_event: dict {close_price, entry_price, correlation_id, ...}
    """
    from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC
    
    # 1. Find matching pair by entry_price with tolerance (S1 fix)
    #    TP fill closes a position opened at entry_price.
    #    Match by entry_price from the fill event, not close_price.
    pair = find_pair_by_entry_price(
        session, 
        fill_event['entry_price'],
        tolerance=session['grid_step'] * 0.1  # 10% of grid step tolerance
    )
    if not pair:
        log.warning(f"TP fill at {fill_event['close_price']} (entry {fill_event['entry_price']}) "
                    f"has no matching ACTIVE pair")
        return
    
    # 1b. Pair-level lock to prevent race with expiry watcher (S4 fix)
    if pair.get('_processing'):
        log.warning(f"Pair {pair['pair_id']} already being processed, skipping TP fill")
        return
    pair['_processing'] = True
    
    try:
        # 2. Update pair with TP fill info (S6 fix: use actual fill prices)
        pair['status'] = 'TP_FILLED'
        pair['tp_fill_time'] = fill_event['timestamp']
        pair['tp_fill_correlation_id'] = fill_event['correlation_id']
        # S6: Use actual close/entry prices from fill, not hardcoded grid_step
        actual_step = fill_event['close_price'] - fill_event['entry_price']
        pair['grid_pnl'] = actual_step * LOT_SIZE_BTC * session['lot_size']
        
        # 3. Determine PE strike for strangle
        pe_strike_target = pair['future_entry_price']  # PE at entry level
        pe_strike, pe_symbol, pe_expiry = await select_pe_parameters(
            target_price=pe_strike_target,
            tolerance=session['params']['strike_tolerance'],
            preferred_expiry=pair['ce_expiry_ddmmyyyy']
        )
        
        # 3b. Check PE premium threshold (S3 fix)
        pe_premium_check = await get_option_premium(pe_symbol)
        if pe_premium_check < session['params'].get('min_pe_premium', 3.0):
            log.info(f"PE premium ₹{pe_premium_check} < min ₹{session['params'].get('min_pe_premium', 3.0)}, "
                     f"skipping strangle. CE orphan at {pair['ce_symbol']} unmanaged.")
            pair['status'] = 'TP_FILLED'  # Leave as orphaned CE without strangle
            save_pair(session, pair)
            send_telegram(f"⚠️ PE premium too low (₹{pe_premium_check}), CE orphan unmanaged")
            return
        
        # 4. Sell PE
        pe_result = await place_option_sell(
            symbol=pe_symbol,
            lots=session['lot_size'],
            order_preference=session['params']['order_preference']
        )
        
        # 5. Update pair with PE info
        pair['pe_strike'] = pe_strike
        pair['pe_symbol'] = pe_symbol
        pair['pe_lots'] = session['lot_size']
        pair['pe_premium'] = pe_result['fill_price']
        pair['pe_order_id'] = pe_result['order_id']
        
        # 6. Create MMM session for the strangle
        mmm_session_id = await create_mmm_session_for_orphan(
            pair_id=pair['pair_id'],  # B3 fix: pass pair_id explicitly
            ce_symbol=pair['ce_symbol'],
            ce_strike=pair['ce_strike'],
            ce_lots=pair['ce_lots'],
            ce_premium=await get_option_premium(pair['ce_symbol']),
            pe_symbol=pe_symbol,
            pe_strike=pe_strike,
            pe_lots=session['lot_size'],
            pe_premium=pe_result['fill_price'],
            expiry=pair['ce_expiry_ddmmyyyy'],
            naming_price=pair['future_entry_price']
        )
        
        # 7. Update pair
        pair['mmm_session_id'] = mmm_session_id
        pair['status'] = 'HANDED_TO_MMM'
        save_pair(session, pair)
        
        # 8. Update session stats
        update_session_stats(session, 
                            grid_pnl_add=pair['grid_pnl'],
                            mmm_session_added=mmm_session_id)
        
        # 9. Emit
        emit_socketio('ssrfo_tp_filled', {
            'pair_id': pair['pair_id'],
            'grid_pnl': pair['grid_pnl'],
            'mmm_session_id': mmm_session_id
        })
        send_telegram(f"💰 SSRFO TP hit @ {fill_event['close_price']} "
                      f"| Grid P&L: ₹{pair['grid_pnl']:.2f} "
                      f"| MMM session: {mmm_session_id}")
    finally:
        pair['_processing'] = False
```

### 7.3 Engine: `process_expiry()`

Called by expiry watcher when a CE is about to expire or has expired:

```python
async def process_expiry(session, pair):
    """
    CE has expired but future still exists. Decide what to do.
    
    Decision tree (evaluated in priority order, first match wins):
      Case 1: market > entry × 1.005      → close future, take profit
      Case 3: market < entry - grid_step   → new CE at entry strike (ATM)
      Case 2: market < entry - reentry_pts → new CE at TP strike (OTM)
      Case 4: everything else              → evaluate premium viability
    """
    from datetime import datetime, timezone  # B4 fix: timezone-aware
    from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC
    
    market_price = await get_btc_price()
    entry = pair['future_entry_price']
    step = session['grid_step']
    
    upper_pct = session['params']['expiry_close_pct']         # 0.5%
    reentry_pts = session['params']['expiry_reentry_pts']     # 200
    
    upper_threshold = entry * (1 + upper_pct / 100)           # e.g., 60300
    reentry_threshold = entry - reentry_pts                   # e.g., 59800
    deep_below_threshold = entry - step                       # e.g., 59500
    
    # Case 1 (highest priority): Market well above entry → close future, take profit
    if market_price > upper_threshold:
        pair['expiry_case'] = 'CASE_1'
        await close_future_at_market(pair)
        await cancel_tp_order(pair)
        pair['status'] = 'CLOSED'
        pair['expiry_action_taken'] = f"Closed future at market ({market_price})"
        
    # Case 3: Market deeply below entry → new CE at entry strike (closer to ATM)
    elif market_price < deep_below_threshold:
        pair['expiry_case'] = 'CASE_3'
        new_ce = await sell_new_ce(pair, target_strike=pair['future_entry_price'])
        update_pair_with_new_ce(pair, new_ce)
        pair['status'] = 'ACTIVE'
        pair['expiry_action_taken'] = f"New CE at {new_ce['strike']} (ATM), expiry {new_ce['expiry']}"
    
    # Case 2: Market moderately below entry → new CE at TP strike (OTM)
    elif market_price < reentry_threshold:
        pair['expiry_case'] = 'CASE_2'
        new_ce = await sell_new_ce(pair, target_strike=pair['future_tp_price'])
        update_pair_with_new_ce(pair, new_ce)
        pair['status'] = 'ACTIVE'
        pair['expiry_action_taken'] = f"New CE at {new_ce['strike']}, expiry {new_ce['expiry']}"
        
    # Case 4 (catch-all): Market near entry → check premium viability
    else:
        pair['expiry_case'] = 'CASE_4'
        premium = await get_option_premium_at_strike(pair['future_tp_price'])
        if premium >= session['params']['min_ce_premium']:
            new_ce = await sell_new_ce(pair, target_strike=pair['future_tp_price'])
            update_pair_with_new_ce(pair, new_ce)
            pair['status'] = 'ACTIVE'
            pair['expiry_action_taken'] = f"New CE at {new_ce['strike']} (premium OK: {premium})"
        else:
            await close_future_at_market(pair)
            await cancel_tp_order(pair)
            pair['status'] = 'CLOSED'
            pair['expiry_action_taken'] = f"Closed future at market (premium too low: {premium})"
    
    save_pair(session, pair)
    emit_socketio('ssrfo_expiry_action', pair_to_dict(pair))
    send_telegram(f"⏰ SSRFO Expiry {pair['expiry_case']}: {pair['expiry_action_taken']}")
```

---

## 8. EventStore Poller Design

### 8.1 Polling Architecture

The SSRFO monitor runs as a background **daemon thread** (like MMM's heartbeat monitor) within the Flask process.

```python
class SSRFOMonitor:
    """
    Polls the grid bot's EventStore SQLite DB for new fill events.
    
    - Read-only access to bot_events_BTCUSD_LONG.db
    - SQLite WAL mode allows concurrent readers with active writer
    - Uses eventlet.spawn (NOT threading.Thread) to match MMM's pattern (B5 fix)
    """
    
    def __init__(self, session_id: str, session: dict):
        self.session_id = session_id
        self.session = session
        self._running = False
        self._poll_interval = session['params']['poll_interval_ms'] / 1000  # 1.0s
        self._expiry_interval = session['params']['expiry_check_interval_s']  # 60s
        self._last_expiry_check = 0
        self._green_thread = None
        
    def start(self):
        """Start polling via eventlet green thread."""
        import eventlet
        self._running = True
        self._green_thread = eventlet.spawn(self._poll_loop)
        log.info(f"[{self.session_id}] SSRFO monitor started")
    
    def stop(self):
        """Stop the polling loop."""
        self._running = False
        log.info(f"[{self.session_id}] SSRFO monitor stopped")
    
    def _poll_loop(self):
        """Main polling loop (runs in eventlet green thread)."""
        import eventlet
        while self._running:
            try:
                self._poll_cycle()
            except Exception as e:
                log.exception(f"[{self.session_id}] Poll cycle error: {e}")
                self._handle_error(e)
            eventlet.sleep(self._poll_interval)
    
    def _poll_cycle(self):
        """Single poll iteration (synchronous, uses tpool for async work)."""
        import eventlet.tpool
        
        # 1. Poll EventStore for new fills
        new_events = self._read_eventstore()
        
        for event in new_events:
            self._route_event(event)
        
        # 2. Run expiry watcher (every 60s)
        now = time.time()
        if now - self._last_expiry_check >= self._expiry_interval:
            self._check_expiries()
            self._last_expiry_check = now
        
        # 3. Run CE ITM buyback check (§3.8)
        self._check_ce_itm_buybacks()
    
    def _read_eventstore(self) -> list:
        """Read new events from gridbot's EventStore SQLite DB."""
        import sqlite3
        db_path = self.session['eventstore_db_path']
        last_ts = self.session['last_processed_timestamp']
        
        # B6 fix: Use context manager to prevent connection leaks
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM events 
                   WHERE timestamp > ? 
                   AND event_type IN (
                       'position_opened', 
                       'position_closed',
                       'opportunistic_position_opened'
                   )
                   ORDER BY timestamp ASC
                   LIMIT 50""",
                (last_ts,)
            )
            events = [dict(row) for row in cursor.fetchall()]
        
        return events
```

### 8.2 Event Routing

```python
def _route_event(self, event: dict):
    """Route an EventStore event to the appropriate handler."""
    import eventlet.tpool
    import asyncio
    
    event_type = event['event_type']
    data = json.loads(event.get('data', '{}'))
    correlation_id = event.get('correlation_id', '')
    
    # Dedup: skip if already processed
    if self._is_processed(correlation_id):
        return
    
    # M2 fix: Handle opportunistic_position_opened the same as position_opened
    if event_type in ('position_opened', 'opportunistic_position_opened'):
        # Grid bot opened a new position (BUY filled in LONG mode)
        fill_data = {
            'entry_price': data.get('entry_price'),
            'size': data.get('size'),
            'correlation_id': correlation_id,
            'timestamp': event['timestamp'],
            'order_id': data.get('order_id'),
        }
        # B5 fix: use eventlet.tpool for async work
        def _run():
            loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.engine.process_entry_fill(self.session, fill_data)
                )
            finally:
                loop.close()
        eventlet.tpool.execute(_run)
    
    elif event_type == 'position_closed':
        # Grid bot closed a position (TP SELL filled in LONG mode)
        fill_data = {
            'close_price': data.get('close_price', data.get('tp_price')),
            'entry_price': data.get('entry_price'),
            'correlation_id': correlation_id,
            'timestamp': event['timestamp'],
            'pnl': data.get('pnl'),
        }
        def _run():
            loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.engine.process_tp_fill(self.session, fill_data)
                )
            finally:
                loop.close()
        eventlet.tpool.execute(_run)
    
    # Update cursor
    self.session['last_processed_timestamp'] = event['timestamp']
    self.session['last_processed_correlation_id'] = correlation_id
    self._save_cursor()
```

### 8.3 Resilience

| Failure Mode | Handling |
|-------------|----------|
| EventStore DB locked | Exponential backoff: 1s → 2s → 4s → max 30s. Log warning. |
| EventStore DB not found | Gridbot not running. Log error, set status to `WAITING_FOR_GRIDBOT`. Retry every 10s. |
| EventStore DB corrupted | Stop polling, alert critical. Manual intervention required. |
| Fill already processed | Skip via `correlation_id` dedup set (persisted in SSRFO DB). |
| Flask process restart | On `init_ssrfo()`, restore monitors from SSRFO DB:
| | 1. Load all sessions with `status == 'RUNNING'`
| | 2. Re-read cursor position from each session's `last_processed_timestamp`
| | 3. Restart `SSRFOMonitor` instances via `eventlet.spawn()`
| | 4. For ACTIVE pairs with CEs nearing expiry, run `_check_expiries()` immediately
| | 5. Verify spawned MMM sessions still exist; alert if any are orphaned |
| CE order placement fails | Retry 3 times with 5s delay. If all fail, create pair as `NAKED_FUTURE`, alert Telegram. |

---

## 9. Options Order Logic

### 9.1 Strike Selection Algorithm

```python
async def select_ce_strike(target_price: float, tolerance: float, 
                           expiry: str) -> Tuple[float, str]:
    """
    Select the best CE strike near the target price.
    
    Args:
        target_price: The TP price of the future (e.g., 60500)
        tolerance: Maximum distance from target (e.g., 100)
        expiry: Expiry string in DDMMYYYY format
    
    Returns:
        (strike, symbol) — Best strike and its trading symbol
    
    Algorithm:
        1. Fetch all available CE strikes for the given expiry
        2. Filter to strikes within [target - tolerance, target + tolerance]
        3. From filtered: prefer strike nearest to target_price
        4. If tied: prefer slightly OTM (higher strike for CE)
        5. If no strikes in range: expand tolerance by 50% and retry once
        6. If still none: return None (caller decides to skip)
    """
    chain_service = get_chain_service()
    chain_data = await chain_service.get_chain(underlying='BTC', expiry=expiry)
    
    calls = chain_data.get('calls', [])
    
    # Filter by tolerance
    candidates = [c for c in calls 
                  if abs(c['strike'] - target_price) <= tolerance]
    
    if not candidates:
        # Expand tolerance
        candidates = [c for c in calls 
                      if abs(c['strike'] - target_price) <= tolerance * 1.5]
    
    if not candidates:
        return None, None
    
    # Score: distance to target, with tiebreak preferring OTM
    def score(c):
        distance = abs(c['strike'] - target_price)
        otm_bonus = -0.1 if c['strike'] >= target_price else 0
        return distance + otm_bonus
    
    best = min(candidates, key=score)
    
    # Verify liquidity
    if best.get('bid_size', 0) < 1:
        log.warning(f"Low liquidity at strike {best['strike']}: bid_size={best.get('bid_size')}")
    
    symbol = build_option_symbol('C', 'BTC', best['strike'], expiry)
    return best['strike'], symbol
```

### 9.2 Expiry Selection Algorithm

```python
async def select_expiry(min_hours: float = 24) -> Tuple[str, datetime]:
    """
    Select the nearest expiry with at least min_hours remaining.
    
    BTC options on Delta Exchange expire at 17:30 IST (12:00 UTC).
    
    Returns:
        (expiry_ddmmyyyy, expiry_utc_datetime)
    """
    chain_service = get_chain_service()
    available = await chain_service.get_available_expiries(underlying='BTC')
    
    now_utc = datetime.now(timezone.utc)
    
    valid_expiries = []
    for exp_str in available:
        exp_dt = parse_expiry_to_utc(exp_str)  # Returns UTC datetime at 12:00
        hours_remaining = (exp_dt - now_utc).total_seconds() / 3600
        
        if hours_remaining >= min_hours:
            valid_expiries.append((exp_str, exp_dt, hours_remaining))
    
    if not valid_expiries:
        raise NoValidExpiryError(f"No expiry with ≥{min_hours}h remaining")
    
    # Pick nearest valid expiry
    valid_expiries.sort(key=lambda x: x[2])
    chosen = valid_expiries[0]
    
    return chosen[0], chosen[1]
```

### 9.3 Order Placement

```python
async def place_option_sell(symbol: str, lots: int, order_preference: str) -> dict:
    """
    Place an option sell order using existing options infrastructure.
    
    Uses place_smart_order() from order_executor.py (B1 fix: correct import path).
    Handles: maker-first, maker-only, market-only order preferences.
    """
    # B1 fix: Import from order_executor (canonical location), NOT options_control
    from webui.backend.routes.options.order_executor import place_smart_order
    from webui.backend.routes.options.options_client import get_unified_client
    
    client = get_unified_client()
    
    result = await place_smart_order(
        client=client,
        product_symbol=symbol,  # Correct param name per order_executor.py
        size=lots,
        side='sell',
        order_preference=order_preference,
        reduce_only=False
    )
    
    return result
```

### 9.4 Symbol Construction

Following Delta Exchange format:

```python
def build_option_symbol(option_type: str, underlying: str, 
                        strike: float, expiry_input: str) -> str:
    """
    Build Delta Exchange option symbol.
    
    Format: {C|P}-{underlying}-{strike}-{DDMMYY}
    Examples:
        C-BTC-60500-210226  (Call, BTC, strike 60500, 21 Feb 2026)
        P-BTC-59500-210226  (Put, BTC, strike 59500, 21 Feb 2026)
    
    B8 fix: Handles both DDMMYYYY (8-char) and DDMMYY (6-char) input.
    """
    prefix = 'C' if option_type.upper() in ('C', 'CALL', 'CE') else 'P'
    
    # Normalize expiry to DDMMYY
    expiry_clean = expiry_input.strip()
    if len(expiry_clean) == 8:
        # DDMMYYYY → DDMMYY (e.g., 21022026 → 210226)
        ddmmyy = expiry_clean[:4] + expiry_clean[6:8]
    elif len(expiry_clean) == 6:
        # Already DDMMYY
        ddmmyy = expiry_clean
    else:
        raise ValueError(f"Invalid expiry format: '{expiry_input}', expected DDMMYYYY or DDMMYY")
    
    strike_str = str(int(strike))
    return f"{prefix}-{underlying}-{strike_str}-{ddmmyy}"
```

---

## 10. MMM Bridge — Auto-Spawning Sessions

### 10.1 When MMM Sessions Are Created

An MMM session is spawned when **a grid TP fills** and the paired CE becomes orphaned:

```
TP fills at 60,000 (future bought @ 59,500 closed)
  → CE @ ~60,000 is orphaned (no future backing it)
  → SSRFO sells PE @ ~59,500 (to create strangle)
  → SSRFO creates MMM session with:
      CE: -1 lot @ 60,000 strike
      PE: -1 lot @ 59,500 strike
  → MMM manages the strangle autonomously
```

### 10.2 MMM Session Creation Logic

```python
async def create_mmm_session_for_orphan(
    pair_id: str,  # B3 fix: explicit pair_id parameter
    ce_symbol: str, ce_strike: float, ce_lots: int, ce_premium: float,
    pe_symbol: str, pe_strike: float, pe_lots: int, pe_premium: float,
    expiry: str, naming_price: float
) -> str:
    """
    Create an MMM session in IMPORT mode for an orphaned CE+PE strangle.
    
    B2 fix: Uses the correct 2-step pattern matching mmm_api.py:
      1. create_session(mode='import', params=...)
      2. initialize_side_from_entry() for each side
    Does NOT pass import_data to create_session (that param doesn't exist).
    
    A2 fix: Includes activity logging and WebSocket emissions to match
    the full MMM start flow rather than bypassing it.
    """
    from webui.backend.routes.mmm.mmm_storage import get_storage
    from webui.backend.routes.mmm.mmm_state import (
        create_session as mmm_create_session,
        initialize_side_from_entry,
        get_session_summary,
    )
    from webui.backend.routes.mmm.mmm_monitor import start_session_monitor
    from webui.backend.routes.mmm.mmm_websocket import (
        emit_status_change, emit_session_created
    )
    from datetime import datetime, timezone
    
    # 1. Generate session ID (A5 fix: use uuid suffix to avoid TOCTOU race)
    import uuid
    session_id = f"mmm-ssrfo-{int(naming_price)}-{uuid.uuid4().hex[:6]}"
    
    # 2. Create session state — step 1: create with params only (B2 fix)
    session = mmm_create_session(
        session_id=session_id,
        mode='import',
        params={
            'desired_ce_premium': ce_premium,
            'desired_pe_premium': pe_premium,
            'initial_lots': ce_lots,
            'expiry': expiry,
            'adjustment_interval': 300,
            'min_trigger_move_pct': 5.0,
            'shift_threshold': 50.0,
            'max_loss_amount': 500.0,
            'close_at_premium': 5.0,
            'auto_close_mins': 5,
            'wind_down_hours_before_expiry': 2.0,
            '_spawned_by': 'ssrfo',
            '_source_pair_id': pair_id,  # B3 fix: now defined
        }
    )
    
    # 3. Initialize sides — step 2: call initialize_side_from_entry (B2 fix)
    initialize_side_from_entry(session, side='ce',
                               strike=ce_strike, premium=ce_premium, lots=ce_lots)
    initialize_side_from_entry(session, side='pe',
                               strike=pe_strike, premium=pe_premium, lots=pe_lots)
    session['entry_time'] = datetime.now(timezone.utc).isoformat()
    
    # 4. Persist
    storage = get_storage()
    storage.save_session(session)
    
    # 5. A2 fix: emit WebSocket events and log activity (match MMM's full flow)
    emit_session_created(session_id, get_session_summary(session))
    
    # 6. Start the MMM heartbeat monitor
    session['strategy_status'] = 'RUNNING'
    session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
    storage.save_session(session)
    emit_status_change(session_id, 'IDLE', 'RUNNING', 'SSRFO auto-spawned')
    start_session_monitor(session_id, session)
    
    log.info(f"Created MMM session {session_id} for orphan pair {pair_id}: "
             f"CE @ {ce_strike}, PE @ {pe_strike}")
    
    return session_id
```

### 10.3 MMM Session Naming Convention

```python
# A5 fix: Session IDs now use uuid suffix instead of sequential scan.
# Format: mmm-ssrfo-{price}-{uuid6}
# Examples: mmm-ssrfo-59500-a1b2c3, mmm-ssrfo-60000-d4e5f6
# This eliminates the O(n²) scan and TOCTOU race condition.
```

### 10.4 Tracking Spawned Sessions

SSRFO tracks all spawned MMM sessions and aggregates their P&L:

```python
async def update_mmm_pnl(session):
    """Fetch P&L from all spawned MMM sessions."""
    from webui.backend.routes.mmm.mmm_storage import get_storage
    
    storage = get_storage()
    total_mmm_pnl = 0.0
    
    for mmm_id in session['spawned_mmm_sessions']:
        mmm_session = storage.get_session(mmm_id)
        if mmm_session:
            total_mmm_pnl += mmm_session.get('realized_pnl', 0)
            total_mmm_pnl += mmm_session.get('unrealized_pnl', 0)
    
    session['total_mmm_pnl'] = total_mmm_pnl
    session['total_pnl'] = (session['total_grid_pnl'] + 
                            session['total_ce_premium_collected'] + 
                            total_mmm_pnl)
```

---

## 11. Expiry Watcher — Edge Cases

### 11.1 Watcher Design

The expiry watcher runs inside the SSRFOMonitor thread, checking every 60 seconds:

```python
async def _check_expiries(self):
    """Check all active pairs for expiring CEs."""
    
    now_utc = datetime.now(timezone.utc)
    
    for pair in self.session['pairs']:
        if pair['status'] != 'ACTIVE':
            continue
        
        if not pair.get('ce_expiry_time'):
            continue
        
        expiry_dt = datetime.fromisoformat(pair['ce_expiry_time'])
        hours_remaining = (expiry_dt - now_utc).total_seconds() / 3600
        
        # Pre-expiry warning (4 hours before)
        if hours_remaining <= 4 and not pair.get('_expiry_warned'):
            emit_socketio('ssrfo_expiry_warning', {
                'pair_id': pair['pair_id'],
                'hours_remaining': round(hours_remaining, 1),
                'entry_price': pair['future_entry_price']
            })
            pair['_expiry_warned'] = True
        
        # CE expired — execute edge case logic
        if hours_remaining <= 0:
            pair['status'] = 'CE_EXPIRED'
            await self.engine.process_expiry(self.session, pair)
```

### 11.2 Case Decision Matrix

| Market Price | Case | Action | Risk | Outcome |
|-------------|------|--------|------|---------|
| > entry + 0.5% | 1 | Close future at market, cancel TP | None | Profit taken, clean exit |
| < entry - 200pts | 2 | New CE at TP strike (OTM) | Future still underwater | New premium + waiting for TP |
| < entry - 500pts | 3 | New CE at entry strike (ATM-ish) | Higher CE premium = higher risk if rally | Higher premium income |
| ≈ entry ± 0.5% | 4a | New CE if premium > min | Small risk | Continue covered call |
| ≈ entry ± 0.5% | 4b | Close future if premium < min | Small P&L | Clean exit, free margin |

### 11.3 Next-Day Handling (from notes: "I need suggestion for next day")

When market opens the next day after CE expiry:

**Strategy for next-day naked futures:**

1.  **Pre-market check** (before 9:00 AM IST): Run expiry watcher once to identify all pairs where CE expired overnight
2.  **For each naked future**, apply the Case 1-4 logic based on current market price
3.  **If gridbot is running**: Let the grid bot continue managing the future's TP. SSRFO will sell a new CE on the next available session with ≥24h expiry
4.  **If gridbot is NOT running**: Close naked futures that have been unhedged for > `max_naked_hours` (configurable, default 12h)

**Configurable parameters for this:**

```yaml
max_naked_hours: 12          # Max hours a future can be without CE
auto_roll_on_expiry: true    # Auto-sell new CE on expiry (Cases 2/3/4a)
expiry_case1_pct: 0.5        # % above entry to trigger Case 1
expiry_case2_points: 200     # Points below entry for Case 2
next_day_check_time: "09:00" # IST time for next-day sweep
```

---

## 12. Safety & Risk Management

### 12.1 Safety Layers

```
Layer 1: PRE-TRADE CHECKS (before every CE/PE sell)
  ├── Guardian signal = GO
  ├── Available margin > required × 1.5
  ├── Total short CE lots < max_ce_exposure_lots
  ├── Active pairs < max_active_pairs
  └── Premium > min_ce_premium

Layer 2: CIRCUIT BREAKER
  ├── 3 consecutive order failures → PAUSE session
  ├── Daily loss > max_daily_loss → STOP session
  ├── Margin utilization > 80% → PAUSE new sells
  └── Reset on manual resume

Layer 3: POSITION RECONCILIATION (every 5 min)
  ├── Read exchange positions via GET /v2/positions
  ├── Compare with SSRFO internal state
  ├── Flag discrepancies
  └── Auto-correct minor issues, alert major ones

Layer 4: EXPIRY SAFETY
  ├── Never let a CE go ITM without action plan
  ├── Alert at T-4h, T-1h before expiry
  ├── Auto-execute expiry cases at T-0
  └── Max naked future hours limit

Layer 5: MMM SESSION MONITORING
  ├── Track health of all spawned MMM sessions
  ├── Alert if MMM session enters BOTH_SIDES_UP
  ├── Aggregate P&L and loss limits
  └── Max total spawned sessions limit
```

### 12.2 Margin Calculation

Before selling a CE, estimate the margin required:

```python
async def check_margin_for_ce_sell(lots: int, strike: float) -> dict:
    """
    Check if sufficient margin is available for CE sell.
    
    Returns:
        {allowed: bool, available: float, required: float, 
         utilization_pct: float, reason: str}
    """
    from bot.api.unified_api_client import UnifiedAPIClient
    from config.loader import get_api_credentials
    
    creds = get_api_credentials()
    client = UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol='BTCUSD',
        enable_websocket=False
    )
    
    # Fetch wallet balance
    balances = await client.get_wallet_balance()
    available = balances.get('available_balance', 0)
    
    # Estimate margin (approximate: ~3-5% of notional for BTC options on Delta)
    notional = strike * 0.001 * lots  # BTC contract multiplier
    estimated_margin = notional * 0.05  # 5% estimate
    
    safety_factor = 1.5
    required = estimated_margin * safety_factor
    
    return {
        'allowed': available >= required,
        'available': available,
        'required': required,
        'utilization_pct': ((balances.get('balance', 0) - available) / 
                           balances.get('balance', 1)) * 100,
        'reason': '' if available >= required 
                  else f"Need ₹{required:.2f} but only ₹{available:.2f} available"
    }
```

### 12.3 Duplicate Prevention (Idempotency)

```python
class ProcessedEventTracker:
    """
    Tracks processed EventStore correlation_ids to prevent duplicate actions.
    Persisted in SSRFO SQLite DB.
    """
    
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                correlation_id TEXT PRIMARY KEY,
                event_type TEXT,
                processed_at REAL,
                action_taken TEXT
            )
        """)
    
    def is_processed(self, correlation_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed_events WHERE correlation_id = ?",
            (correlation_id,)
        ).fetchone()
        return row is not None
    
    def mark_processed(self, correlation_id: str, event_type: str, 
                       action: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO processed_events VALUES (?, ?, ?, ?)",
            (correlation_id, event_type, time.time(), action)
        )
        self._conn.commit()
```

---

## 13. REST API Design

### 13.1 Endpoints

Blueprint: `ssrfo_bp = Blueprint('ssrfo', __name__, url_prefix='/api/ssrfo')`

#### Session Management

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|-------------|----------|
| `POST` | `/session/create` | Create new SSRFO session | `{symbol, params?}` | `{success, session}` |
| `GET` | `/sessions` | List all sessions | — | `{success, sessions[], count}` |
| `GET` | `/session/<id>` | Get session details | — | `{success, session}` |
| `POST` | `/session/<id>/start` | Start polling & trading | — | `{success, message}` |
| `POST` | `/session/<id>/pause` | Pause (keep pairs) | — | `{success, message}` |
| `POST` | `/session/<id>/resume` | Resume from pause | — | `{success, message}` |
| `POST` | `/session/<id>/stop` | Stop session | — | `{success, message}` |
| `DELETE` | `/session/<id>` | Delete session | — | `{success, message}` |

#### Pair Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/session/<id>/pairs` | All pairs with status |
| `GET` | `/session/<id>/pairs/active` | Only active pairs |
| `GET` | `/session/<id>/pairs/<pair_id>` | Single pair detail |
| `POST` | `/session/<id>/pairs/<pair_id>/retry-ce` | Retry failed CE sell |
| `POST` | `/session/<id>/pairs/<pair_id>/close` | Force close a pair |

#### MMM Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/session/<id>/mmm-sessions` | All spawned MMM sessions |
| `GET` | `/session/<id>/mmm-pnl` | Aggregated MMM P&L |

#### Configuration & Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/session/<id>/config` | Update params at runtime |
| `GET` | `/session/<id>/config` | Get current config |
| `GET` | `/session/<id>/stats` | P&L breakdown |
| `GET` | `/session/<id>/dashboard` | Full dashboard data |
| `GET` | `/health` | Module health check |

#### Manual Controls

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/session/<id>/sell-ce` | Manual CE sell for a price level |
| `POST` | `/session/<id>/reconcile` | Force position reconciliation |
| `POST` | `/session/<id>/sweep-expiries` | Manual expiry sweep |

### 13.2 Example: Create Session

```json
// POST /api/ssrfo/session/create
{
    "symbol": "BTCUSD",
    "params": {
        "strike_tolerance": 100,
        "min_expiry_hours": 24,
        "min_ce_premium": 3.0,
        "order_preference": "maker_first",
        "max_active_pairs": 20,
        "max_ce_exposure_lots": 100,
        "expiry_close_pct": 0.5,
        "expiry_reentry_pts": 200,
        "max_naked_hours": 12,
        "auto_roll_on_expiry": true,
        "mmm_auto_create": true,
        "telegram_alerts": true
    }
}

// Response 201
{
    "success": true,
    "session": {
        "session_id": "ssrfo-btc-1",
        "status": "IDLE",
        "symbol": "BTCUSD",
        "grid_step": 500,
        "lot_size": 5,
        "params": { ... },
        "pairs": [],
        "spawned_mmm_sessions": [],
        "total_pnl": 0.0,
        "created_at": "2026-02-21T15:30:00Z"
    }
}
```

---

## 14. WebSocket Events

### 14.1 Event Catalog

| Event | Trigger | Payload |
|-------|---------|---------|
| `ssrfo_status_change` | Session status changes | `{session_id, old_status, new_status}` |
| `ssrfo_ce_sold` | CE sell order filled | `{pair_id, entry_price, ce_strike, ce_premium, ce_symbol}` |
| `ssrfo_ce_failed` | CE sell order failed | `{pair_id, entry_price, error, will_retry}` |
| `ssrfo_ce_skipped` | CE sell skipped (low premium/margin) | `{pair_id, entry_price, reason}` |
| `ssrfo_tp_filled` | Grid TP filled, CE orphaned | `{pair_id, tp_price, grid_pnl, mmm_session_id}` |
| `ssrfo_mmm_spawned` | New MMM session created | `{pair_id, mmm_session_id, ce_strike, pe_strike}` |
| `ssrfo_expiry_warning` | CE expiring soon | `{pair_id, hours_remaining, entry_price}` |
| `ssrfo_expiry_action` | Expiry case executed | `{pair_id, case, action_taken}` |
| `ssrfo_safety_alert` | Safety check triggered | `{session_id, check, severity, message}` |
| `ssrfo_pnl_update` | P&L updated (every 30s) | `{session_id, grid_pnl, premium_pnl, mmm_pnl, total_pnl}` |
| `ssrfo_reconciliation` | Position reconciliation result | `{session_id, ok, discrepancies[]}` |
| `ssrfo_heartbeat` | Monitor alive signal (every 10s) | `{session_id, pairs_active, last_poll_ts}` |

### 14.2 Implementation

```python
# ssrfo_websocket.py

_socketio = None

def init_websocket(socketio):
    global _socketio
    _socketio = socketio

def emit(event: str, data: dict, namespace: str = '/'):
    if _socketio:
        _socketio.emit(event, data, namespace=namespace)
```

---

## 15. Frontend Dashboard

### 15.1 Dashboard Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ SSRFO Dashboard                                     [Start] [Stop]    │
├─────────────────────┬──────────────────────────────────────────────────┤
│                     │                                                  │
│  SESSION STATUS     │  P&L SUMMARY                                    │
│  ● RUNNING          │  ┌──────────────────────────────────────────────┐│
│                     │  │ Grid P&L:      $45.00  ████████████         ││
│  Since: 2h 30m      │  │ CE Premium:    $28.50  ████████             ││
│  Pairs Active: 8    │  │ MMM Sessions:  $12.30  ████                 ││
│  Pairs Total: 23    │  │ ────────────────────────                    ││
│  MMM Sessions: 5    │  │ TOTAL P&L:     $85.80  ████████████████     ││
│                     │  └──────────────────────────────────────────────┘│
├─────────────────────┴──────────────────────────────────────────────────┤
│                                                                        │
│  ACTIVE PAIRS                                                          │
│  ┌──────────┬────────┬──────────┬──────────┬──────────┬───────────────┐│
│  │ Entry    │ TP     │ CE Strike│ CE Prem  │ Expiry   │ Status        ││
│  ├──────────┼────────┼──────────┼──────────┼──────────┼───────────────┤│
│  │ 82,000   │ 82,500 │ 82,500   │ ₹4.20    │ 14h rem  │ ● ACTIVE     ││
│  │ 81,500   │ 82,000 │ 82,000   │ ₹3.80    │ 14h rem  │ ● ACTIVE     ││
│  │ 81,000   │ 81,500 │ 81,500   │ ₹5.10    │ 38h rem  │ ● ACTIVE     ││
│  │ 80,500   │ 81,000 │ —        │ —        │ —        │ ○ NAKED      ││
│  └──────────┴────────┴──────────┴──────────┴──────────┴───────────────┘│
│                                                                        │
│  SPAWNED MMM SESSIONS                                                  │
│  ┌──────────────────────┬────────┬──────────┬──────────┬──────────────┐│
│  │ Session ID           │ CE/PE  │ Status   │ P&L      │ Actions      ││
│  ├──────────────────────┼────────┼──────────┼──────────┼──────────────┤│
│  │ mmm-ssrfo-81000-1    │ 81500/ │ RUNNING  │ +$3.20   │ [View] [Stop]││
│  │                      │ 81000  │          │          │              ││
│  │ mmm-ssrfo-80500-1    │ 81000/ │ RUNNING  │ +$1.50   │ [View] [Stop]││
│  │                      │ 80500  │          │          │              ││
│  └──────────────────────┴────────┴──────────┴──────────┴──────────────┘│
│                                                                        │
│  CONFIGURATION                                         [Edit Config]  │
│  Strike Tolerance: ±100  │  Min Expiry: 24h  │  Min Premium: ₹3.00   │
│  Max Active Pairs: 20    │  Order Pref: maker_first                   │
│                                                                        │
│  ACTIVITY LOG                                                          │
│  15:30:02  CE sold: C-BTC-82500-220226 @ ₹4.20 for entry @ 82000     │
│  15:28:14  TP filled @ 81500 → Grid P&L: ₹2.50 → MMM mmm-ssrfo-..   │
│  15:25:30  CE sold: C-BTC-82000-220226 @ ₹3.80 for entry @ 81500     │
│  15:20:00  ⚠ Expiry warning: pair ce_81000 expires in 4h             │
└────────────────────────────────────────────────────────────────────────┘
```

### 15.2 Frontend Files to Create

```
webui/frontend/src/pages/
  └── SSRFODashboard.jsx          # Main dashboard page

webui/frontend/src/components/ssrfo/
  ├── SSRFOSessionControls.jsx    # Start/Stop/Pause buttons
  ├── SSRFOPairTable.jsx          # Active futures↔CE pair table
  ├── SSRFOMMMPanel.jsx           # Spawned MMM sessions list
  ├── SSRFOPnLSummary.jsx         # P&L breakdown cards
  ├── SSRFOConfigEditor.jsx       # Runtime config editor
  └── SSRFOActivityLog.jsx        # Real-time event log
```

### 15.3 Router Addition

Add route in the React router:

```jsx
<Route path="/ssrfo" element={<SSRFODashboard />} />
```

Add navigation link in sidebar.

---

## 16. Configuration Parameters

### 16.1 Default Configuration

```python
SSRFO_DEFAULT_PARAMS = {
    # ─── Strike Selection ───
    'strike_tolerance': 100,         # ±points for CE/PE strike selection
    'prefer_otm': True,              # Prefer OTM strike when tied
    'max_lots_per_strike': 15,       # M5: Max short lots at any single strike
    
    # ─── Expiry Selection ───
    'min_expiry_hours': 24,          # Minimum hours to expiry for CE
    'max_expiry_hours': 72,          # Maximum hours (avoid long-dated)
    
    # ─── Lot Sizing ───
    'lots_ratio': 1,                 # CE lots per future lot (1:1)
    
    # ─── Premium ───
    'min_ce_premium': 3.0,           # Minimum CE premium to sell (₹)
    'min_pe_premium': 3.0,           # Minimum PE premium for strangle (₹)
    'max_spread_pct': 20.0,          # Max bid-ask spread (%) to accept
    
    # ─── CE ITM Buyback (§3.8) ───
    'ce_buyback_multiplier': 3.0,    # Buy back CE if mark > sold × this
    'ce_buyback_delta': 0.70,        # Buy back CE if delta exceeds this
    'max_ce_loss': 100.0,            # Hard stop per CE position (₹)
    
    # ─── Polling ───
    'poll_interval_ms': 1000,        # EventStore polling interval
    'expiry_check_interval_s': 60,   # Expiry watcher interval
    'reconciliation_interval_s': 300, # Position reconciliation
    
    # ─── Order Execution ───
    'order_preference': 'maker_first', # maker_first | maker_only | market_only
    'order_retry_count': 3,           # Retries on order failure
    'order_retry_delay_s': 5,         # Delay between retries
    
    # ─── Expiry Cases ───
    'expiry_close_pct': 0.5,          # Case 1: % above entry to close
    'expiry_reentry_pts': 200,        # Case 2: points below entry
    'auto_roll_on_expiry': True,      # Auto-sell new CE on expiry
    'max_naked_hours': 12,            # Max hours without CE
    
    # ─── MMM Bridge ───
    'mmm_auto_create': True,          # Auto-create MMM for orphans
    'mmm_adjustment_interval': 300,   # MMM heartbeat interval
    'mmm_min_trigger_pct': 5.0,       # MMM trigger threshold
    'mmm_max_loss_per_session': 500,  # ₹ max loss per MMM session
    
    # ─── Safety ───
    'max_active_pairs': 20,           # Max concurrent pairs
    'max_ce_exposure_lots': 100,      # Max total short CE lots
    'max_pe_exposure_lots': 100,      # Max total short PE lots
    'margin_safety_factor': 1.5,      # Margin multiplier
    'circuit_breaker_failures': 3,    # Consecutive failures to trip
    'max_daily_loss': 2000,           # ₹ daily loss limit
    'max_spawned_mmm_sessions': 10,   # Max concurrent MMM sessions
    
    # ─── Notifications ───
    'telegram_alerts': True,
    'telegram_daily_summary': True,
    'telegram_summary_time': '17:30', # IST
}
```

### 16.2 Validation Rules

```python
SSRFO_PARAM_VALIDATION = {
    'strike_tolerance': {'type': float, 'min': 50, 'max': 500},
    'min_expiry_hours': {'type': float, 'min': 1, 'max': 168},
    'min_ce_premium': {'type': float, 'min': 0.1, 'max': 100},
    'poll_interval_ms': {'type': int, 'min': 500, 'max': 10000},
    'max_active_pairs': {'type': int, 'min': 1, 'max': 200},
    'max_ce_exposure_lots': {'type': int, 'min': 1, 'max': 1000},
    'margin_safety_factor': {'type': float, 'min': 1.0, 'max': 3.0},
    'circuit_breaker_failures': {'type': int, 'min': 1, 'max': 10},
    'max_daily_loss': {'type': float, 'min': 100, 'max': 50000},
    'order_preference': {'type': str, 'choices': ['maker_first', 'maker_only', 'market_only']},
}
```

---

## 17. Integration with Existing Systems

### 17.1 Blueprint Registration in app.py

Add to `webui/backend/app.py` after the MMM blueprint registration block:

```python
# ─── SSRFO (Futures + Options) ───
try:
    from webui.backend.routes.ssrfo import ssrfo_bp, init_ssrfo, init_websocket as init_ssrfo_websocket
    app.register_blueprint(ssrfo_bp)
    print(f"✅ Registered ssrfo blueprint (/api/ssrfo)")
    init_ssrfo_websocket(socketio)
    print(f"✅ SSRFO WebSocket initialized")
    init_ssrfo()
    print(f"✅ SSRFO initialized and sessions restored")
except Exception as e:
    print(f"⚠️ Could not register ssrfo blueprint: {e}")
    log.warning(f"SSRFO routes not available: {e}")
```

### 17.2 Dependencies on Existing Modules

| SSRFO uses | From module | For |
|------------|-------------|-----|
| `EventStore` SQLite DB | Grid bot (`bot/strategy/modules/event_store.py`) | Fill detection (read-only) |
| `OptionsChainService` | `webui/backend/options_chain/chain_service.py` | Strike/expiry data |
| `place_smart_order()` | `webui/backend/routes/options/options_control.py` | CE/PE sell orders |
| `get_unified_client()` | `webui/backend/routes/options/options_control.py` | Exchange API client |
| `create_session()` | `webui/backend/routes/mmm/mmm_state.py` | MMM session creation |
| `start_session_monitor()` | `webui/backend/routes/mmm/mmm_monitor.py` | MMM heartbeat start |
| `get_storage()` | `webui/backend/routes/mmm/mmm_storage.py` | MMM session persistence |
| `get_signal()` | `webui/backend/trading_control.py` | Guardian GO/STOP check |
| `get_api_credentials()` | `config/loader.py` | API keys |
| Grid config | `config.yaml` → `config/loader.py` | step, lot_size |

### 17.3 Config.yaml Addition (Optional)

SSRFO config lives in its own SQLite DB per session, but we can add a reference section to `config.yaml`:

```yaml
ssrfo:
  enabled: true
  default_symbol: BTCUSD
  eventstore_db: data/bot_events_BTCUSD_LONG.db
```

### 17.4 PM2 Ecosystem (No Changes Needed)

SSRFO runs inside the `webui-backend` Flask process — no new PM2 entry needed. The `webui-backend` process already has `autorestart: true`.

---

## 18. Testing Plan

### 18.1 Unit Tests

```
tests/test_ssrfo_engine.py
  ├── test_process_entry_fill_normal
  ├── test_process_entry_fill_dedup
  ├── test_process_entry_fill_safety_block
  ├── test_process_tp_fill_normal
  ├── test_process_tp_fill_no_matching_pair
  ├── test_process_expiry_case1_above_entry
  ├── test_process_expiry_case2_below_200
  ├── test_process_expiry_case3_below_500
  ├── test_process_expiry_case4a_premium_ok
  ├── test_process_expiry_case4b_premium_low

tests/test_ssrfo_options.py
  ├── test_select_ce_strike_exact_match
  ├── test_select_ce_strike_within_tolerance
  ├── test_select_ce_strike_prefers_otm
  ├── test_select_ce_strike_no_match_expands
  ├── test_select_expiry_minimum_24h
  ├── test_select_expiry_no_valid
  ├── test_build_option_symbol_call
  ├── test_build_option_symbol_put

tests/test_ssrfo_state.py
  ├── test_session_creation
  ├── test_pair_creation
  ├── test_pair_state_transitions
  ├── test_find_pair_by_tp_price
  ├── test_dedup_correlation_id

tests/test_ssrfo_expiry.py
  ├── test_expiry_detection_timing
  ├── test_pre_expiry_warning
  ├── test_expired_ce_case_routing
  ├── test_naked_future_timeout
```

### 18.2 Integration Tests (Testnet)

```
1. Start gridbot on Delta Exchange testnet
2. Start SSRFO session (POST /api/ssrfo/session/create + start)
3. Trigger grid fill by moving BTC price → verify CE is sold
4. Verify pair record created in SSRFO DB
5. Trigger TP fill → verify PE is sold + MMM session created
6. Verify MMM heartbeat is running
7. Wait for CE expiry → verify expiry case logic executes
8. Stop SSRFO → restart Flask → verify monitor restores
```

### 18.3 Manual Smoke Test Commands

```bash
# Create session
curl -X POST http://localhost:5555/api/ssrfo/session/create \
  -H 'Content-Type: application/json' \
  -d '{"symbol": "BTCUSD"}'

# Start session
curl -X POST http://localhost:5555/api/ssrfo/session/ssrfo-btc-1/start

# Check status
curl http://localhost:5555/api/ssrfo/session/ssrfo-btc-1

# View pairs
curl http://localhost:5555/api/ssrfo/session/ssrfo-btc-1/pairs

# View MMM sessions
curl http://localhost:5555/api/ssrfo/session/ssrfo-btc-1/mmm-sessions

# Force reconciliation
curl -X POST http://localhost:5555/api/ssrfo/session/ssrfo-btc-1/reconcile

# Stop
curl -X POST http://localhost:5555/api/ssrfo/session/ssrfo-btc-1/stop
```

---

## 19. Implementation Phases

### Phase 1: Foundation (Estimated: 2-3 days)

| Step | Task | Files |
|------|------|-------|
| 1.1 | Create directory structure | `webui/backend/routes/ssrfo/` |
| 1.2 | Implement `ssrfo_config.py` | Params, validation, defaults |
| 1.3 | Implement `ssrfo_state.py` | Dataclasses, enums, helpers |
| 1.4 | Implement `ssrfo_storage.py` | SQLite DB, CRUD, WAL mode |
| 1.5 | Implement `ssrfo_api.py` (skeleton) | Blueprint, session CRUD only |
| 1.6 | Register blueprint in `app.py` | Import + register |
| 1.7 | Test: create/list/delete sessions via curl | Manual verification |

### Phase 2: Core Polling & CE Selling (Estimated: 2-3 days)

| Step | Task | Files |
|------|------|-------|
| 2.1 | Implement `ssrfo_monitor.py` | EventStore poller, thread management |
| 2.2 | Implement `ssrfo_options.py` | Strike selection, expiry selection, order placement |
| 2.3 | Implement `ssrfo_engine.py` (entry fills) | `process_entry_fill()` |
| 2.4 | Add start/stop/pause API endpoints | Complete `ssrfo_api.py` |
| 2.5 | Implement `ssrfo_safety.py` (basic) | Guardian check, margin check |
| 2.6 | Test: start SSRFO, trigger grid fill, verify CE sell | Integration test on testnet |

### Phase 3: TP Fill + MMM Bridge (Estimated: 2-3 days)

| Step | Task | Files |
|------|------|-------|
| 3.1 | Implement `ssrfo_engine.py` (TP fills) | `process_tp_fill()` |
| 3.2 | Implement `ssrfo_mmm_bridge.py` | MMM session creation, naming, tracking |
| 3.3 | Test: trigger TP, verify PE sell + MMM spawn | Integration test |
| 3.4 | Implement MMM P&L aggregation | `update_mmm_pnl()` |

### Phase 4: Expiry Handling (Estimated: 1-2 days)

| Step | Task | Files |
|------|------|-------|
| 4.1 | Implement `ssrfo_expiry_watcher.py` | Expiry detection, case routing |
| 4.2 | Implement `ssrfo_engine.py` (expiry cases) | `process_expiry()` with Cases 1-4 |
| 4.3 | Test: let CE expire, verify case execution | Time-based test |
| 4.4 | Add next-day sweep logic | Scheduled check |

### Phase 5: Safety & Monitoring (Estimated: 1-2 days)

| Step | Task | Files |
|------|------|-------|
| 5.1 | Complete `ssrfo_safety.py` | Circuit breaker, reconciliation, limits |
| 5.2 | Implement `ssrfo_websocket.py` | All events from catalog |
| 5.3 | Implement `ssrfo_telegram.py` | Alerts, daily summary |
| 5.4 | Position reconciliation | Exchange vs internal state |

### Phase 6: Frontend (Estimated: 2-3 days)

| Step | Task | Files |
|------|------|-------|
| 6.1 | `SSRFODashboard.jsx` | Main page layout |
| 6.2 | `SSRFOPairTable.jsx` | Live pair tracking table |
| 6.3 | `SSRFOMMMPanel.jsx` | Spawned sessions panel |
| 6.4 | `SSRFOPnLSummary.jsx` | P&L breakdown |
| 6.5 | `SSRFOConfigEditor.jsx` | Runtime config |
| 6.6 | Router + sidebar integration | Navigation |

### Phase 7: Hardening (Estimated: 1-2 days)

| Step | Task |
|------|------|
| 7.1 | Write unit tests for all engine functions |
| 7.2 | Full end-to-end test on testnet |
| 7.3 | Load test: simulate 50 rapid fills |
| 7.4 | Documentation and AI_CONTEXT.md update |
| 7.5 | Code review, edge case audit |

**Total estimated time: 11-18 days**

---

## 20. Open Questions & Stuck Points

### 20.1 Questions to Resolve Before Building

#### Q1: Contract Multiplier Confirmation
The notes show `profit = 500 × 0.001 × 1 = ₹5`. But with `lot_size: 5` in config.yaml for BTCUSD, is the profit per lot or per order?
- If per lot: `₹0.50/lot × 5 lots = ₹2.50 per grid cycle`
- If per order: the multiplier might be `0.001 × lot_size`

**Need:** Confirm the exact BTC perpetual contract value on Delta Exchange India. Is it 0.001 BTC per contract? And does the grid bot trade `lot_size=5` contracts per grid level?

#### Q2: Options Lot Size vs Futures Lot Size
When selling CE options, does "1 lot of CE" mean the same as "1 lot of BTC future" on Delta Exchange? Or do they have different contract sizes?

**Need:** Confirm if BTC options on Delta Exchange India have the same contract multiplier (0.001 BTC) as BTC perpetual futures. If different, the 1:1 ratio needs adjustment.

#### Q3: EventStore Event Data Schema
What exact fields does a `POSITION_OPENED` event contain in the `data` JSON?

**Need:** Either sample the DB (`sqlite3 data/bot_events_BTCUSD_LONG.db "SELECT data FROM events WHERE event_type='position_opened' LIMIT 3"`) or read the EventStore code more carefully to confirm available fields: `entry_price`, `size`, `order_id`, etc.

#### Q4: Option Chain Data Availability
Does `OptionsChainService` always have fresh data, or does it need to be manually refreshed? What's the cache TTL?

**Need:** Verify the chain service is always warm when SSRFO needs strike data, especially during off-hours or when options chain is thin.

#### Q5: MMM Import Mode Full Behavior
When creating an MMM session in import mode:
- Does it automatically find the positions on the exchange?
- Or does SSRFO need to pass the exact symbol/lots and MMM trusts it?
- Does MMM do its own position verification?

**Need:** Read MMM import flow to confirm how much data SSRFO must provide vs what MMM discovers itself.

#### Q6: Guardian Signal Scope
The Guardian monitors grid bot positions. Does `get_signal()` return a global GO/STOP, or is it per-symbol?
- Can Guardian return STOP for the grid bot but SSRFO should still manage existing pairs?
- Should SSRFO have its own Guardian-like safety layer?

**Need:** Decide if SSRFO should pause ALL activity when Guardian says STOP, or only pause new CE sells while still managing expiries.

#### Q7: Stuck Point (Image Reference)
The user referenced an image at:
```
image-1771666836609.jpeg (VS Code chat images)
```
**This image could not be loaded/viewed by the AI.** 

**Please describe what you're stuck on**, and I'll incorporate the solution into the plan. Common candidates:
- How to handle CE going ITM before expiry?
- How to handle rapid market moves (3+ grid levels in seconds)?
- How to link the grid bot process to the webui process?
- PE strike selection when grid step doesn't align with options strikes?
- What happens when CE expiry and TP fill happen simultaneously?

#### Q8: Multiple Grid Entries in Quick Succession
If market drops 3 grid levels in 10 seconds, the grid bot fills 3 BUYs rapidly. SSRFO needs to sell 3 CEs quickly.

**Questions:**
- Should CEs share the same expiry, or can they differ?
- Should SSRFO batch CE sells (3 orders at once), or process sequentially?
- Rate limiting: Delta Exchange allows ~10 req/s. With 3 CEs + the grid orders, is there rate limit risk?

#### Q9: Same-Strike CEs from Different Grid Levels
If grid step is 500, and options strikes are at 500-point intervals:
- grid entry @ 60,000 → CE @ 60,500
- grid entry @ 60,500 → CE @ 61,000
- What if both map to the same CE strike due to ±100 tolerance?

**Should:** SSRFO add to existing short position (increase lots at same strike)? Or find the next available strike?

#### Q10: PE Expiry Matching on Orphan
When selling PE to form a strangle after TP fill:
- The orphaned CE has a specific expiry. The PE should ideally match.
- But what if that expiry is now < 24h away?
- Should SSRFO use the next expiry for PE? (Mismatch means MMM manages a calendar strangle — is that OK?)

### 20.2 Additional Suggestions for Your "Next Day" Question

From the notes (page 6): "I need suggestion for next day. How can I tackle?"

**Here is the recommended next-day protocol:**

#### Morning Routine (9:00 AM IST)

1. **Sweep all pairs**: Run `process_expiry()` on every pair where CE expired since last check
2. **For naked futures**: Apply Case 1-4 logic based on current market price
3. **For orphaned options managed by MMM**: Check MMM session health
4. **Re-evaluate premiums**: If IV has changed significantly overnight, adjust `min_ce_premium` threshold

#### Specific Next-Day Scenarios

| Scenario | What Happened | Action |
|----------|--------------|--------|
| CE expired, market UP | Future is in profit, no CE | **Case 1**: Close future, book profit |
| CE expired, market FLAT | Future near entry, no CE | **Case 4**: Sell new CE if premium is good, else close |
| CE expired, market DOWN | Future underwater, no CE | **Case 2/3**: Sell new CE (closer ATM for more premium) |
| MMM session active overnight | Strangle still running | Let MMM continue. It has wind-down and close-at-5 logic |
| Grid bot was OFF overnight | No new fills | SSRFO stays idle. No new pairs. Manage existing ones. |
| Multiple CEs expired overnight | Several naked futures | Batch process all in order of largest exposure first |

#### Automated Next-Day Sweep

```python
async def next_day_sweep(session):
    """Run at configured time (default 9:00 AM IST) each day."""
    
    naked_pairs = [p for p in session['pairs'] 
                   if p['status'] in ('CE_EXPIRED', 'NAKED_FUTURE')]
    
    if not naked_pairs:
        log.info(f"Next-day sweep: no naked futures")
        return
    
    log.info(f"Next-day sweep: {len(naked_pairs)} naked futures to process")
    
    # Sort by exposure (largest first)
    naked_pairs.sort(key=lambda p: abs(p['future_entry_price']), reverse=True)
    
    for pair in naked_pairs:
        await process_expiry(session, pair)
    
    send_telegram(f"📊 SSRFO next-day sweep: processed {len(naked_pairs)} naked futures")
```

---

## 21. Risk Register

### 21.1 Identified Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | CE goes deep ITM before TP fills | Medium | High: CE loss > grid profit | Monitor CE delta; auto-buyback if delta > 0.7 |
| R2 | Grid bot stops unexpectedly | Low | Medium: Naked CEs without future backing | Detect gridbot absence; alert; manage CEs independently |
| R3 | EventStore DB grows very large | Low | Low: Slow polling | Index on timestamp; use LIMIT in queries; periodic cleanup |
| R4 | MMM session fails after creation | Medium | Medium: Unmanaged strangle | Monitor MMM health; fallback to simple close-at-5 |
| R5 | Rapid grid fills overwhelm SSRFO | Medium | Medium: Delayed CE sells | Batch processing; priority queue; rate awareness |
| R6 | Exchange rate limiting | Low | High: Orders rejected | Shared rate limiter across all modules; exponential backoff |
| R7 | Options chain data stale/missing | Low | Medium: Wrong strike selected | Chain data TTL check; fallback to last known; alert |
| R8 | BTC options liquidity thin (no bids) | Medium | Medium: CE stuck, can't enter at desired price | Liquidity check before sell; skip if bid_size < 1; wider spread tolerance |
| R9 | CE and TP fill simultaneously | Low | Low: Race condition on pair status | Lock pair during state transition; idempotent operations |
| R10 | Flask process restart loses monitors | Low | Medium: Pairs unmonitored | Restore monitors on `init_ssrfo()` like MMM does |
| R11 | Margin exhaustion from too many short options | Medium | Critical: Liquidation risk | Margin guardian check before every sell; hard cap on exposure |
| R12 | Mismatch between SSRFO state and exchange | Low | High: Phantom positions | Reconciliation every 5 min; alerts on discrepancy |

### 21.2 Risk Appetite Defaults

```python
# Maximum acceptable total short options exposure
MAX_NOTIONAL_EXPOSURE_USD = 10000

# Maximum number of active SSRFO pairs
MAX_ACTIVE_PAIRS = 20

# Circuit breaker: pause after N consecutive failures
CIRCUIT_BREAKER_THRESHOLD = 3

# Max daily loss across all SSRFO activity (excluding MMM)
MAX_DAILY_LOSS_USD = 2000

# Max margin utilization before blocking new sells
MAX_MARGIN_UTILIZATION_PCT = 70
```

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **CE** | Call Option (right to buy at strike price) |
| **PE** | Put Option (right to sell at strike price) |
| **TP** | Take-Profit order |
| **Grid Step** | Price distance between grid levels (500 for BTC) |
| **Covered Call** | Selling CE while holding the underlying (future) |
| **Orphaned CE** | A short CE whose paired future has been closed (TP filled) |
| **Strangle** | Combination of CE + PE at different strikes |
| **MMM** | Money Mind & Method — existing options algo |
| **Pair** | A `FutureOptionPair` — one grid entry + its paired CE |
| **Naked Future** | A future position without a CE hedge |
| **EventStore** | SQLite DB where grid bot logs all events |
| **Maker-first** | Try limit order at mid-price before market order |
| **Delta Exchange** | The exchange used for BTC futures and options |
| **WAL Mode** | SQLite Write-Ahead Logging — enables concurrent readers |

## Appendix B: Contract Specifications (Delta Exchange India)

| Product | Type | Contract Size | Tick Size | Lot Size (config) |
|---------|------|--------------|-----------|-------------------|
| BTCUSD | Perpetual Future | 0.001 BTC | 0.5 USD | 5 |
| C-BTC-{strike}-{expiry} | Call Option | 0.001 BTC (TBC) | TBD | TBD |
| P-BTC-{strike}-{expiry} | Put Option | 0.001 BTC (TBC) | TBD | TBD |

> **Action item:** Confirm options contract specs match futures specs on Delta Exchange.

## Appendix C: Example Full Lifecycle

```
─── Day 1, 10:00 AM ─── Market at 82,500 ───────────────────────────────

1. SSRFO session "ssrfo-btc-1" is RUNNING
2. Grid bot running with step=500, lot_size=5

─── 10:15 AM ─── Market drops to 82,000 ──────────────────────────────

3. Grid bot fills: BUY 5 lots BTC @ 82,000 (TP → 82,500)
4. EventStore: POSITION_OPENED @ 82,000
5. SSRFO detects fill (1s poll)
6. SSRFO selects CE: strike 82,500, expiry 22Feb2026 (>24h)
7. SSRFO sells: -5 C-BTC-82500-220226 @ ₹4.20 premium/lot
8. Pair created: ACTIVE (future@82000 ↔ CE@82500)
9. Telegram: "🟢 CE sold: C-BTC-82500-220226 @ ₹4.20"

─── 10:30 AM ─── Market drops to 81,500 ──────────────────────────────

10. Grid bot fills: BUY 5 lots BTC @ 81,500 (TP → 82,000)
11. SSRFO sells: -5 C-BTC-82000-220226 @ ₹3.80 premium/lot
12. Pair created: ACTIVE (future@81500 ↔ CE@82000)

─── 11:45 AM ─── Market recovers to 82,000 ────────────────────────────

13. Grid bot TP fills: SELL 5 lots @ 82,000 (was bought @ 81,500)
14. Grid P&L: 500 × 0.001 × 5 = ₹2.50
15. SSRFO detects TP fill
16. CE @ 82,000 is orphaned
17. SSRFO sells PE: -5 P-BTC-81500-220226 @ ₹3.50
18. SSRFO creates MMM session: "mmm-ssrfo-81500-a1b2c3"
    - CE: -5 @ 82,000
    - PE: -5 @ 81,500
19. MMM heartbeat starts, manages the strangle
20. Telegram: "💰 TP hit @ 82,000 | Grid P&L: ₹2.50 | MMM: mmm-ssrfo-81500-a1b2c3"

─── 12:30 PM ─── Market continues to 82,500 ─────────────────────────

21. Grid bot TP fills: SELL 5 lots @ 82,500 (was bought @ 82,000)
22. Grid P&L: ₹2.50
23. CE @ 82,500 is orphaned
24. SSRFO sells PE: -5 P-BTC-82000-220226
25. SSRFO creates MMM session: "mmm-ssrfo-82000-d4e5f6"
26. Telegram: "💰 TP hit @ 82,500 | Grid P&L: ₹2.50 | MMM: mmm-ssrfo-82000-d4e5f6"

─── Day 2, 5:30 PM IST ─── Options expiry ─────────────────────────────

(If any pairs still have 22Feb2026 CEs, expiry watcher kicks in)

27. CE at 82,500 expires → No active pair (was already handed to MMM)
28. MMM sessions may have already wound down or closed at ₹5
29. No naked futures in SSRFO (all TPs already filled)

─── P&L Summary for Day 1-2 ──────────────────────────────────────────

Grid P&L:        ₹2.50 + ₹2.50 = ₹5.00
CE Premium:      (₹4.20 + ₹3.80) × 5 lots × 0.001 BTC = ₹0.04 per lot
                 → Total CE premium collected: ₹4.20×5 + ₹3.80×5 = ₹40.00
PE Premium:      ₹3.50×5 + (from 2nd TP) = additional ₹17.50+
MMM Session PnL: Depends on MMM management (~₹5-20 estimated)
─────────────────────────────────
Estimated Total:  ₹62 - ₹82 vs ₹5.00 grid-only

NOTE: Premium values depend heavily on IV at time of sell. 
      The ₹4.20/lot CE premium is illustrative. In low-IV 
      environments, premiums may be ₹1-2 per lot.
```

---

*End of SSRFO Planning Document*
