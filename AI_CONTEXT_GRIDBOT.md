# AI Context — AsyncGridBot (Grid Trading Bot)

**Last Updated:** March 2, 2026  
**Branch:** `SSR` (production)  
**Exchange:** Delta Exchange India  
**Product:** BTCUSD perpetual futures (product_id: 27)

---

## 1. What Is This Bot?

A **grid trading bot** for Bitcoin perpetual futures on Delta Exchange. It places limit orders at fixed price intervals (a "grid") and profits from price oscillating within a range. Each filled entry order immediately gets a take-profit (TP) order at one grid step away.

**Core loop:** Place BUY → wait for fill → place SELL TP → wait for TP fill → place next BUY → repeat.

The bot runs 24/7 as a PM2-managed process (`gridbot-btc-live`). It has a React WebUI for monitoring, a Guardian risk system that can halt trading, and an event-sourced SQLite store for crash-safe state recovery.

---

## 2. Strategy Walkthrough

### 2.1 LONG Mode (Current Production Config)

```
Grid Config:
  Reference:  $66,500
  Lower:      $63,000
  Upper:      $100,000
  Step:       $500
  TP Offset:  $500 (= step)
  Lot Size:   5 contracts
  Max Pos:    20
```

**How it works:**

1. **Startup:** Bot calculates the nearest grid level below the current market price. If BTC is at $66,710, the nearest grid BUY level is $66,000 (`ref - step` = $66,500 - $500 = $66,000`).

2. **Entry (BUY):** Bot places a limit BUY at $66,000 (post-only, maker order). It waits.

3. **Fill:** Price drops to $66,000 and the BUY fills. The bot:
   - Records the position in the event store
   - Immediately places a SELL TP limit order at $66,500 (entry + step)
   - Calculates the next BUY level at $65,500 (entry - step)
   - Places the next BUY limit at $65,500

4. **TP Fill:** Price rises to $66,500 and the SELL TP fills. The bot:
   - Closes the position, records profit
   - The grid is now clear at that level; next BUY can re-enter at $66,000

5. **Multiple positions:** If price keeps dropping, the bot keeps placing BUYs one step apart:
   ```
   Position 1: BUY $66,000 → TP $66,500
   Position 2: BUY $65,500 → TP $66,000
   Position 3: BUY $65,000 → TP $65,500
   ...up to 20 positions max
   ```

6. **Profit:** Each completed cycle earns the price difference of one grid step ($500) on the lot size (5 contracts).

**Visual:**
```
$67,000  ─── upper grid ───────────────── (no orders placed this high)
$66,500  ─── TP SELL ← ← ← ← ← ← ←┐
$66,000  ─── BUY entry ──────────────┘   (filled → TP placed above)
$65,500  ─── Next BUY (placed after $66,000 fills)
$65,000  ─── (placed if $65,500 fills)
  ...
$63,000  ─── Lower bound (no orders below this)
```

### 2.2 SHORT Mode

Mirror of LONG. The bot sells high and buys back low.

1. **Entry (SELL):** Place limit SELL at the nearest grid level above current price
2. **Fill:** SELL fills → place BUY TP at (entry - step) below
3. **TP Fill:** BUY TP fills → position closed, profit captured
4. **Next entry:** Place next SELL one step higher

```
SHORT Mode Grid:
  SELL entry $67,000 → TP BUY $66,500
  SELL entry $67,500 → TP BUY $67,000
  SELL entry $68,000 → TP BUY $67,500
```

**Key differences from LONG:**
- `short_lot_size` config (can differ from long `lot_size`)
- Position sorting: LONG sorts lowest-first; SHORT sorts highest-first
- Grid direction: LONG places BUYs below price; SHORT places SELLs above price
- TP direction: LONG TP = entry + step; SHORT TP = entry − step

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   AsyncGridBot (orchestrator)             │
│                   1,941 lines — wires everything          │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │PositionActor│  │ OrderActor   │  │ SagaCoordinator │ │
│  │ (state)     │  │ (API calls)  │  │ (workflows)     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘ │
│         │                │                    │          │
│  ┌──────┴────────────────┴────────────────────┴────────┐ │
│  │              7 Extracted Modules                     │ │
│  │  guardian_handler  health_monitor   exchange_sync    │ │
│  │  ws_lifecycle      fill_processor   grid_engine      │ │
│  │  recovery_actions                                    │ │
│  └─────────────────────────────────────────────────────┘ │
│                          │                               │
│  ┌───────────────────────┴──────────────────────────┐    │
│  │  Event Store (SQLite)    Grid Calculator (pure)  │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
         │                    │
    Delta Exchange        Guardian Bot
    (WebSocket + REST)    (risk signals)
```

### Module Responsibilities

| Module | Lines | What It Does |
|--------|-------|-------------|
| `async_gridbot.py` | 1,941 | Orchestrator — constructs all modules, wires callbacks, manages lifecycle |
| `guardian_handler.py` | 690 | Reads Guardian GO/STOP signals, halts/resumes trading, retries missed orders |
| `health_monitor.py` | 563 | Heartbeat (20s), monitoring dashboard, watchdog (60s), TP retry queue |
| `exchange_sync.py` | 713 | Full exchange sync on startup, orphaned order cleanup, maintenance detection |
| `ws_lifecycle.py` | 575 | WebSocket connection, ticker/order/position handlers, REST fallback |
| `fill_processor.py` | 812 | Fill dedup, BUY/SELL fill routing, saga creation, missed fill processing |
| `grid_engine.py` | 846 | Order placement, grid level calculations, safety checks, initial order logic |
| `recovery_actions.py` | 528 | Safety gatekeeper (5 min), fill polling fallback (60s), reconciliation |

---

## 4. Key Design Patterns

### 4.1 Actor Model (Zero-Lock Concurrency)

State is managed by **actor objects** with mailboxes. External code sends messages; the actor processes them one-at-a-time in a loop. No locks, no race conditions.

- **PositionActor** — owns `open_tranches`, `pending_buy/sell`, position index
- **OrderActor** — owns `_active_orders`, handles all API calls to place/cancel orders

Messages: `ask(type, data, timeout)` (request-reply) or `tell(type, data)` (fire-and-forget).

```python
# Example: ask position actor for current state
state = await position_actor.ask("GET_STATE", {})
positions = state["open_tranches"]

# Example: tell order actor to place a buy
result = await order_actor.ask("PLACE_BUY", {
    "price": 66000.0,
    "size": 5,
    "tag": "GBOT_BUY_66000_1772427737"
}, timeout=15.0)
```

### 4.2 Saga Pattern (Multi-Step Workflows)

Fills trigger **sagas** — ordered sequences of steps with compensation (rollback) on failure.

**BUY fill saga (LONG mode):**
| Step | Action | On Failure |
|------|--------|-----------|
| 1 | Add position to state | Remove position |
| 2 | Clear pending buy | No-op |
| 3 | Place TP order (or schedule retry if Guardian STOP) | — |
| 4 | Place next grid BUY | — |

Each saga has a 30s timeout. Saga IDs are tied to `order_id + timestamp` for dedup.

### 4.3 Event Sourcing (Crash-Safe State)

All state changes are recorded as events in a **SQLite database** (`data/bot_events_BTCUSD_LONG.db`).

On startup, the bot replays events to rebuild state:
```
POSITION_OPENED events − POSITION_CLOSED events = current open positions
```

**Critical rule:** The bot only tracks positions it created (via its own events). It never "adopts" positions from the exchange that were placed manually or by other bots.

Key event types: `POSITION_OPENED`, `POSITION_CLOSED`, `ORDER_PLACED`, `ORDER_FILLED`, `PENDING_BUY_SET`, `PENDING_BUY_CLEARED`, `SAGA_STARTED`, `SAGA_COMPLETED`, `TP_RETRY_SCHEDULED`.

### 4.4 Callback Wiring (Module Isolation)

Modules never import each other. The orchestrator wires them together via `set_runtime_refs()` callbacks at startup:

```python
# Example: HealthMonitor needs fill count from FillProcessor
self.health_monitor.set_runtime_refs(
    _get_fills_processed=lambda: self.fill_processor._fills_processed,
    _tp_retry_callback=self.recovery_actions.process_tp_retry_queue,
)
```

This keeps modules independently importable and testable.

---

## 5. Fill Processing Pipeline

```
                    ┌─────────────────┐
                    │  Delta Exchange  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        WebSocket       FillMonitor    Fill Polling
        (real-time)     (REST, 30s)    (REST, 60s)
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  fill_processor  │
                    │  process_fill()  │
                    │  (dedup by ID)   │
                    └────────┬────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
           BUY fill (LONG)         SELL fill (LONG)
           SELL fill (SHORT)       BUY fill (SHORT)
                 │                       │
           Entry Saga              TP Close Saga
           ┌─────────┐            ┌──────────┐
           │1.Add pos │            │1.Close   │
           │2.Clear   │            │  position│
           │  pending │            │2.Clear TP│
           │3.Place TP│            │3.Place   │
           │4.Next    │            │  next    │
           │  grid    │            │  entry   │
           └─────────┘            └──────────┘
```

**Three fill sources** (all deduplicated):
1. **WebSocket** — real-time, primary path
2. **FillMonitor** — REST polling every 30s, catches orders that WebSocket missed
3. **Fill Polling Fallback** — REST polling every 60s, catches fills via `/v2/fills` endpoint

Fill IDs are tracked in `_seen_fill_ids` set (FillProcessor). Both `fill_id` and `order_id` are checked to prevent double-processing.

---

## 6. Guardian Risk System

The **Guardian** is a separate process that monitors market risk and publishes GO/STOP signals.

**Monitored parameters:**
- Implied Volatility (IV) and Realized Volatility (RV)
- Account PnL vs max loss threshold (₹25,000)
- Position count and liquidation distance
- RSI thresholds

**Signal flow:**
```
Guardian Process → writes signal to event store → GridBot reads every 10s
```

**GO** = trading allowed. **STOP** = halt all new entries, cancel pending orders.

**Rules:**
- No Guardian signal = STOP (safety default)
- Stale signal (>120s) while running = emergency shutdown
- When Guardian goes STOP: all pending entry orders are cancelled
- When Guardian returns to GO: missed grid orders are retried automatically

**TP orders during STOP:** If a fill occurs during Guardian STOP and TP can't be placed, the TP is scheduled for retry via `TP_RETRY_QUEUE` (max 5 retries).

---

## 7. Startup Sequence

```
1.  Load config (v5.0 YAML → grid params, safety limits)
2.  Create actors (PositionActor, OrderActor, SagaCoordinator)
3.  Replay events from SQLite → rebuild open positions
4.  Create all 7 modules (guardian, health, exchange, ws, fill, grid, recovery)
5.  Start actors (begin message processing)
6.  Reconcile orphaned orders (clean up from previous run)
7.  Full exchange sync (catch fills that happened while bot was down)
8.  Connect WebSocket → authenticate → subscribe channels
9.  Fetch current price via REST
10. Cleanup misaligned orders
11. Place initial grid order (or sync existing exchange order)
12. Start FillMonitor
13. Reset heartbeat timer
14. Launch 15 async tasks:
    - GuardianMonitor, Heartbeat, Monitoring, HealthCheck, Watchdog
    - ExchangeMonitor, WSMessages, RestFallback, WSHealthMonitor
    - ReconProcessor, SafetyGatekeeper, FillPolling
    - StateGuardianMonitor, StateReconciliation
    - FillMonitor task
```

---

## 8. File Structure

```
bot/
├── api/
│   ├── async_delta_client.py      # Async REST/WS client for Delta Exchange
│   ├── unified_api_client.py      # Unified abstraction over WS + REST
│   ├── circuit_breaker.py         # API resilience
│   └── ...
├── delta_websocket/
│   ├── async_ws_manager.py        # WebSocket connection manager (1,217 lines)
│   └── ...
├── strategy/
│   ├── async_gridbot.py           # ORCHESTRATOR (1,941 lines)
│   ├── actors/
│   │   ├── base_actor.py          # Actor base class (mailbox + message loop)
│   │   ├── position_actor.py      # Position state (1,290 lines)
│   │   └── order_actor.py         # Order execution (1,145 lines)
│   ├── sagas/
│   │   ├── fill_processing_saga.py    # Entry + TP fill workflows (1,309 lines)
│   │   ├── position_closing_saga.py   # Emergency close workflow
│   │   └── saga_coordinator.py        # Saga lifecycle manager
│   ├── modules/
│   │   ├── guardian_handler.py    # Guardian GO/STOP signals (690 lines)
│   │   ├── health_monitor.py      # Heartbeat + watchdog (563 lines)
│   │   ├── exchange_sync.py       # Exchange reconciliation (713 lines)
│   │   ├── ws_lifecycle.py        # WebSocket management (575 lines)
│   │   ├── fill_processor.py      # Fill handling + routing (812 lines)
│   │   ├── grid_engine.py         # Order placement logic (846 lines)
│   │   ├── recovery_actions.py    # Safety loops (528 lines)
│   │   ├── grid_calculator.py     # Pure grid math (640 lines)
│   │   ├── event_store.py         # SQLite event sourcing (494 lines)
│   │   └── mode_state_manager.py  # LONG/SHORT mode tracking
│   ├── monitors/
│   │   └── fill_monitor.py        # REST fill polling safety net
│   ├── reconciliation/            # Standalone reconciliation engine
│   ├── recovery/                  # Startup/Guardian recovery engines
│   └── simple_state_coordinator.py # State coordination between modules
├── utils/
│   ├── human_logger.py            # Human-readable log messages
│   └── notifier.py                # Telegram notifications
└── logs/
    └── pm2-gridbot-btc-live.log   # Main bot log (PM2 managed)

config.yaml                        # Bot configuration
data/
├── bot_events_BTCUSD_LONG.db     # SQLite event store
├── monitoring_snapshot.json        # WebUI data
└── reconciliation/                # Reconciliation action queue

webui/
├── backend/                       # Python Flask backend
│   ├── app.py                     # Main server
│   ├── routes/                    # API endpoints
│   └── services/                  # Business logic
└── frontend/                      # React + TypeScript + Tailwind
    ├── src/
    └── build/                     # Production build
```

---

## 9. Configuration Reference

### config.yaml — Key Sections

```yaml
version: "5.0"
trading_mode: live

symbols:
  BTCUSD:
    enabled: true
    mode: LONG
    product_id: 27
    grid:
      geometry:
        reference: 66500      # Center of grid
        lower: 63000           # Bottom bound (no BUYs below this)
        upper: 100000          # Top bound
        step: 500              # Distance between grid levels
      limits:
        max_open_positions: 20 # Max concurrent positions
        lot_size: 5            # Contracts per order (LONG)
        short_lot_size: 5      # Contracts per order (SHORT)
      behavior:
        strict_grid: true      # Only place on exact grid levels
        rung_snap_mode: below  # Snap to grid level below price
        tick_size: 0.5         # Exchange minimum price increment
    safety:
      max_account_loss_inr: 25000   # Max loss before Guardian STOP
      min_liquidation_distance_pct: 50  # Min distance to liquidation
```

### Key Behavioral Rules

| Rule | Detail |
|------|--------|
| **One pending entry at a time** | Only 1 BUY (LONG) or 1 SELL (SHORT) pending at any time |
| **Grid alignment** | All orders snap to grid levels (multiples of step from reference) |
| **Post-only orders** | Entry orders use post-only flag (maker-only, no taker fees) |
| **TP is always placed** | Every filled entry immediately gets a TP order (or retry queue) |
| **Max 20 positions** | Hard limit prevents over-exposure |
| **No position adoption** | Bot never tracks positions it didn't create |
| **Order tags** | All orders tagged `GBOT_BUY_66000_xxx` for identification |

---

## 10. Expected Ideal Behavior

### Normal Operation
```
[Heartbeat every 20s]  Positions: 3/20 | Price: $66,710 | ✅ ACTIVE
[Guardian every 10s]   🟢 GO - Trading allowed
[Fill polling 60s]     ✅ No missed fills
[Safety check 5min]    ✅ All positions have TP orders
```

### On BUY Fill
```
⚡ FILL: BUY 5 @ $66,000 (order 1202892369)
  → Position added: entry=$66,000, TP=$66,500
  → TP SELL placed: 5 @ $66,500 (order 1202892400)
  → Next BUY placed: 5 @ $65,500 (order 1202892412)
  Positions: 1/20
```

### On TP Fill
```
⚡ FILL: SELL 5 @ $66,500 (TP for position at $66,000)
  → Position closed, profit: $500/contract
  → Grid level $66,000 available for re-entry
  Positions: 0/20
```

### On Guardian STOP
```
🛡️ Guardian: 🔴 STOP - High volatility (IV: 85%)
  → Cancelled pending BUY at $65,500
  → TP orders preserved (positions still protected)
  → No new entries until GO
```

### On Guardian GO (after STOP)
```
🛡️ Guardian: 🟢 GO - Trading allowed
  → Retrying missed grid orders...
  → Placed BUY at $65,500 (missed during STOP)
```

### On Crash + Restart
```
[Startup] Replaying events from SQLite...
  → Restored 3 open positions from event store
  → Reconciling with exchange...
  → All TP orders confirmed present on exchange
  → Placing next grid BUY at $64,500
  ✅ Bot resumed from crash-safe state
```

---

## 11. Safety Layers

| Layer | Component | Check Interval | What It Does |
|-------|-----------|---------------|-------------|
| 1 | **Guardian** | 5s (external) | IV/RV, PnL, position risk → GO/STOP |
| 2 | **Health Monitor** | 20s heartbeat | Uptime, memory, WS health |
| 3 | **Watchdog** | 10s | Detects frozen event loop (60s timeout) |
| 4 | **Safety Gatekeeper** | 5 min | Checks all positions have TP orders |
| 5 | **Fill Polling** | 60s | Catches missed WebSocket fills via REST |
| 6 | **Fill Monitor** | 30s | Verifies tracked orders via REST order status |
| 7 | **Exchange Sync** | Startup only | Full reconciliation on every restart |
| 8 | **TP Retry Queue** | Per health check | Retries failed TP placements (max 5) |

---

## 12. Common Maintenance Operations

### Stop the bot
```bash
pm2 stop gridbot-btc-live
```

### Start the bot
```bash
pm2 start gridbot-btc-live
```

### View logs (live)
```bash
pm2 logs gridbot-btc-live
```

### Check for errors
```bash
grep -c "ERROR\|CRITICAL\|Traceback" bot/logs/pm2-gridbot-btc-live.log
```

### Check heartbeat
```bash
grep "ACTIVE" bot/logs/pm2-gridbot-btc-live.log | tail -1
```

### Verify all tasks running
```bash
grep -E "Safety gatekeeper|Fill polling|Reconciliation action" bot/logs/pm2-gridbot-btc-live.log | head -5
```

### Check current positions
```bash
curl -s http://localhost:5555/api/positions | python3 -m json.tool
```

---

## 13. Critical Rules for AI Developers

1. **NEVER change fill processing logic** without extensive testing — fills are money
2. **NEVER let the bot adopt exchange positions** — it only tracks its own event-sourced positions
3. **NEVER remove deduplication** on fills — three sources can fire for the same fill
4. **Always use loguru** (`from loguru import logger as log`) — not stdlib `logging`
5. **Always use `if human_log:` guards** when calling human_log methods
6. **Modules never import each other** — use callbacks via `set_runtime_refs()`
7. **Config lives in `config.yaml`** — support v4.0 (single symbol) and v5.0 (multi-symbol) formats
8. **Order tags start with `GBOT_`** — used to identify bot orders vs manual orders
9. **Event store is append-only** — never delete events, only add new ones
10. **TP orders must survive shutdown** — they protect positions; never cancel TP orders on stop

---

## 14. Refactoring History

The bot was refactored from a monolithic 5,770-line file into 7 focused modules across 42 micro-phases (Phases 0–9). The orchestrator (`async_gridbot.py`) went from 5,770 lines to 1,941 lines (−66%).

Bugs found during audits:
- **P1:** simple_state_coordinator using old method name (1 bug)
- **P2:** Stale callback reference in set_runtime_refs (1 bug)
- **P4:** Early state init before module constructed + wrong import path (2 bugs)
- **P5:** Init ordering, wrong dict keys, stale counter, wrong dedup set (4 bugs)
- **P6:** Zero bugs
- **P7:** Wrong logger (stdlib instead of loguru) — made 3 tasks invisible (1 bug)
- **P8:** Zero bugs

All bugs were fixed and verified with live bot test before merge.
