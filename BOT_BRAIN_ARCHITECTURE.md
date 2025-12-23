# 🧠 GridBot Brain Architecture

**Complete connection order and data flow documentation**

Last Updated: November 9, 2025

---

## 📋 Table of Contents

1. [Startup Sequence](#startup-sequence)
2. [Module Initialization Order](#module-initialization-order)
3. [Runtime Event Flow](#runtime-event-flow)
4. [Data Flow](#data-flow)
5. [Key Connection Points](#key-connection-points)
6. [Module Dependencies](#module-dependencies)
7. [Thread Safety](#thread-safety)
8. [Callback Wiring](#callback-wiring)

---

## 🚀 Startup Sequence

### Phase 1: Entry Point (`bot/run.py`)

```
bot/run.py
  │
  ├─→ 1. Load environment files
  │   ├─→ secrets/api_keys.env (API credentials)
  │   ├─→ .env (main configuration)
  │   └─→ grid_config.env (grid parameters)
  │
  ├─→ 2. Setup logging system
  │   ├─→ bot/utils/logging_setup.py
  │   └─→ Create bot/logs/bot.log
  │
  ├─→ 3. Load trading mode (Demo vs Live)
  │   └─→ bot/utils/env_loader.py
  │
  ├─→ 4. Validate safety systems
  │   ├─→ bot/safety/loss_limits.py
  │   └─→ Verify Guardian + Trader limits align
  │
  ├─→ 5. Initialize global monitors
  │   ├─→ bot/safety/volatility_monitor.py (RV calculator)
  │   ├─→ bot/volatility/iv_rv_tracker.py (IV/RV tracker)
  │   └─→ bot/liquidation/integrated_monitor.py
  │
  └─→ 6. Call run_grid_strategy()
      └─→ bot/strategy/gridbot.py
```

---

### Phase 2: GridBot Initialization (`bot/strategy/gridbot.py`)

**Module initialization happens in strict dependency order:**

```
GridBot.__init__()
  │
  ├─→ 1. GridCalculator (Pure Logic - No Dependencies)
  │   • File: bot/strategy/modules/grid_calculator.py
  │   • Role: Calculate grid levels, TP prices
  │   • Dependencies: NONE
  │
  ├─→ 2. PositionManager (State Owner)
  │   • File: bot/strategy/modules/position_manager.py
  │   • Role: Manage positions, pending orders, state
  │   • Dependencies: GridCalculator
  │   • Creates: threading.RLock() (state lock)
  │
  ├─→ 3. FillDetector (Event Processor)
  │   • File: bot/strategy/modules/fill_detector.py
  │   • Role: Deduplicate fills, queue processing
  │   • Dependencies: PositionManager (uses its lock)
  │   • Creates: Queue for sequential processing
  │
  ├─→ 4. DeltaClient (API Client)
  │   • File: bot/api/delta_client.py
  │   • Role: REST API calls to Delta Exchange
  │   • Dependencies: NONE (independent)
  │
  ├─→ 5. OrderManager (Order Operations)
  │   • File: bot/strategy/modules/order_manager.py
  │   • Role: Place/cancel orders, aggressive polling
  │   • Dependencies: DeltaClient, GridCalculator, PositionManager
  │
  ├─→ 6. Reconciliation (Exchange Sync)
  │   • File: bot/strategy/modules/reconciliation.py
  │   • Role: Sync state with exchange, adopt orphans
  │   • Dependencies: OrderManager, PositionManager, GridCalculator
  │
  ├─→ 7. VolatilityHandler (Safety Logic)
  │   • File: bot/strategy/modules/volatility_handler.py
  │   • Role: Handle volatility halts/recovery
  │   • Dependencies: GridCalculator, PositionManager, OrderManager
  │
  ├─→ 8. WebSocketManager (Connection Manager)
  │   • File: bot/delta_websocket/ws_manager.py
  │   • Role: Manage WebSocket connection, subscriptions
  │   • Dependencies: NONE (independent)
  │
  ├─→ 9. WebSocketHandler (Event Router)
  │   • File: bot/strategy/modules/websocket_handler.py
  │   • Role: Route WebSocket events to handlers
  │   • Dependencies: WebSocketManager
  │
  ├─→ 10. Fill Handlers (Mode-Specific Logic)
  │   • Files:
  │     - bot/strategy/handlers/long_handler.py
  │     - bot/strategy/handlers/short_handler.py
  │   • Role: Process fills for LONG/SHORT mode
  │   • Dependencies: GridBot instance (all modules)
  │
  └─→ 11. Monitoring Systems (5 Layers)
      ├─→ Layer 1: bot/monitoring/price_health.py
      ├─→ Layer 2: bot/monitoring/pre_order_logger.py
      ├─→ Layer 3: bot/monitoring/tp_verification.py
      ├─→ Layer 4: bot/monitoring/anomaly_detection.py
      └─→ Layer 5: bot/monitoring/predictive_display.py
```

---

## 🔗 Module Initialization Order (Critical!)

**⚠️ WARNING: This order MUST be maintained. Changing it will cause crashes!**

| Order | Module | File | Dependencies | Why This Order? |
|-------|--------|------|--------------|-----------------|
| 1 | **GridCalculator** | `modules/grid_calculator.py` | None | Pure logic, no state |
| 2 | **PositionManager** | `modules/position_manager.py` | GridCalculator | Owns state lock |
| 3 | **FillDetector** | `modules/fill_detector.py` | PositionManager lock | Needs lock for thread safety |
| 4 | **DeltaClient** | `api/delta_client.py` | None | Independent REST client |
| 5 | **OrderManager** | `modules/order_manager.py` | GridCalc, PositionMgr, DeltaClient | Needs all above to place orders |
| 6 | **Reconciliation** | `modules/reconciliation.py` | OrderMgr, PositionMgr, GridCalc | Needs OrderMgr to sync |
| 7 | **VolatilityHandler** | `modules/volatility_handler.py` | All above | Coordinates halt logic |
| 8 | **WebSocketManager** | `delta_websocket/ws_manager.py` | None | Independent connection |
| 9 | **WebSocketHandler** | `modules/websocket_handler.py` | WebSocketManager | Routes to all above |
| 10 | **Fill Handlers** | `handlers/long_handler.py` | GridBot instance | Needs full bot context |
| 11 | **Monitoring** | `monitoring/*.py` | All above | Observes everything |

---

## 🔄 Runtime Event Flow

### WebSocket Price Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WebSocket receives price update                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. WebSocketManager parses data                             │
│    • Extract price, timestamp                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. WebSocketHandler routes to callback                      │
│    • Call: _on_price_update(price)                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. GridBot._on_price_update()                               │
│    • Update self.current_price                              │
│    • Update self.last_price_update (timestamp)              │
│    • Call PriceHealthMonitor.update()                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. AnomalyDetectionSystem checks                            │
│    • Price jump detection                                   │
│    • WebSocket staleness check                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Decision: Does price trigger action?                     │
│    • Check if pending order filled                          │
│    • Check if new grid level reached                        │
└─────────────────────────────────────────────────────────────┘
```

---

### WebSocket Fill Event Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WebSocket receives fill event                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. WebSocketHandler routes to FillDetector                  │
│    • Call: process_websocket_fill(fill_data)                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. FillDetector.process_websocket_fill()                    │
│    • Deduplicate (check if already processed)               │
│    • Add to processing queue                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Queue worker processes fill (sequential)                 │
│    • Call: _on_fill_processed(fill_data)                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. GridBot._on_fill_processed()                             │
│    • Determine fill type (BUY or SELL)                      │
│    • Route to appropriate handler                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────┬──────────────────────────────────────┐
│ 6a. LongFillHandler  │  6b. ShortFillHandler                │
│     (BUY fills)      │      (SELL fills)                    │
└──────────────────────┴──────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Update PositionManager                                   │
│    • Add new position or update existing                    │
│    • Clear pending order                                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. Place TP order (Take Profit)                             │
│    • Calculate TP price (GridCalculator)                    │
│    • Call OrderManager.place_tp()                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. Place next grid order (if capacity available)            │
│    • Calculate next level (GridCalculator)                  │
│    • Call OrderManager.place_order()                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. Persist state                                           │
│     • PositionManager.persist_runtime_state()               │
│     • Save to: bot/logs/runtime_state.json                  │
└─────────────────────────────────────────────────────────────┘
```

---

### Order Placement Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Decision to place order                                  │
│    • From: Fill handler, Reconciliation, or Heartbeat       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PreOrderDecisionLogger (Layer 2 Monitoring)              │
│    • Log decision context                                   │
│    • Record: price, mode, reason                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PriceHealthMonitor check (Layer 1 Monitoring)            │
│    • Verify price is fresh (<10s old)                       │
│    • Block order if price stale                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. OrderManager.place_order()                               │
│    • Build order payload                                    │
│    • Call DeltaClient REST API                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Update PositionManager                                   │
│    • Store pending order info                               │
│    • Update pending_buy or pending_sell                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Start Aggressive Polling (Nov 7 Fix)                     │
│    • Background thread starts                               │
│    • Poll every 2 seconds for 30 seconds                    │
│    • Call: DeltaClient.get_order(order_id)                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Detect fill (within 2-4 seconds)                         │
│    • If filled: Trigger FillDetector manually               │
│    • Stop polling once fill detected                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. AnomalyDetectionSystem (Layer 4 Monitoring)              │
│    • Track order placement rate                             │
│    • Alert if too many orders without TP                    │
└─────────────────────────────────────────────────────────────┘
```

---

### Heartbeat Loop (Every 10-15 seconds)

```
GridBot._heartbeat()
  │
  ├─→ 1. Volatility Safety Check
  │   └─→ VolatilityHandler.check_pending_order_safety()
  │
  ├─→ 2. Write Monitoring Snapshot (WebUI)
  │   └─→ MonitoringDataWriter.write_snapshot()
  │       └─→ Output: data/monitoring_snapshot.json
  │
  ├─→ 3. Persist Runtime State
  │   └─→ PositionManager.persist_runtime_state()
  │       └─→ Output: bot/logs/runtime_state.json
  │
  ├─→ 4. Process TP Retry Queue
  │   └─→ Retry failed TP placements
  │
  ├─→ 5. Enforce Single Pending Order Invariant
  │   ├─→ LONG mode: Reconciliation.ensure_single_correct_pending_buy()
  │   └─→ SHORT mode: Reconciliation.ensure_single_correct_pending_sell()
  │
  ├─→ 6. Check Price Staleness (WebSocket Starvation Protection)
  │   └─→ If >30s since last update:
  │       └─→ GridBot._fetch_price_via_rest_api()
  │
  └─→ 7. Check for Missed Fills (REST API Backup)
      └─→ Query exchange for pending order status
          └─→ If filled but missed: Trigger fill processing
```

---

## 📊 Data Flow

### State Storage

```
Runtime State:
  PositionManager
    ↓
  bot/logs/runtime_state.json
    • open_tranches (positions)
    • pending_buy / pending_sell
    • session_tag
    • capacity info

Monitoring Data:
  GridBot (all modules)
    ↓
  MonitoringDataWriter
    ↓
  data/monitoring_snapshot.json
    • bot_status
    • 5 monitoring layers
    • trading_condition
    • predictive scenarios

Logs:
  All modules
    ↓
  bot/logs/bot.log
    • Rotated daily
    • Max 7 backups
    • Structured format
```

---

### WebUI Integration

```
GridBot
  ↓
MonitoringDataWriter.write_snapshot()
  ↓
data/monitoring_snapshot.json
  ↓
WebUI Backend (Flask)
  ↓
API Endpoints:
  • /api/monitoring
  • /api/bot-actions/next
  • /api/anomalies
  ↓
WebUI Frontend (React)
  ↓
User Interface
```

---

## 🔑 Key Connection Points

### 1. Dependency Injection (Constructor)

**Pattern: Pass dependencies through constructor**

```python
# Example: OrderManager initialization
self.order_mgr = OrderManager(
    api_client=self.delta_client,        # ← Injected REST client
    grid_calculator=self.grid_calc,      # ← Injected calculator
    position_manager=self.position_mgr,  # ← Injected state manager
    product_id=self.product_id,
    lot_size=lot,
    tick_size=TICK_SIZE
)
```

**Why:** Clean dependencies, easy testing, no global state

---

### 2. Callback Wiring (Event-driven)

**Pattern: Register callbacks after initialization**

```python
# WebSocket events → GridBot methods
self.ws_handler.setup_callbacks(
    on_price_update=self._on_price_update,
    on_fill=self.fill_detector.process_websocket_fill
)

# Fill processing → Fill handler
self.fill_detector.set_fill_callback(self._on_fill_processed)

# Order placement → Aggressive polling
self.order_mgr.set_fill_callback(self.fill_detector.process_websocket_fill)

# Monitoring → Order manager
self.order_mgr.set_monitoring_systems(
    price_monitor=self.price_monitor,
    pre_order_logger=self.pre_order_logger,
    anomaly_detector=self.anomaly_detector
)
```

**Why:** Loose coupling, event-driven architecture, easy to extend

---

### 3. Shared Lock (Thread Safety)

**Pattern: Single lock owned by PositionManager, shared with others**

```python
# PositionManager creates the lock
class PositionManager:
    def __init__(self):
        self.state_lock = threading.RLock()

# FillDetector uses the same lock
self.fill_detector = FillDetector(
    state_lock=self.position_mgr.state_lock  # ← Share lock
)

# All state mutations protected by same lock
with self.state_lock:
    # Modify state here
    pass
```

**Why:** Prevent race conditions, atomic operations, thread safety

---

## 🧵 Thread Safety

### Critical Sections (Protected by Lock)

```
state_lock = threading.RLock()

Protected Operations:
  ├─→ PositionManager.add_position()
  ├─→ PositionManager.remove_position()
  ├─→ PositionManager.set_pending_buy()
  ├─→ PositionManager.clear_pending_buy()
  ├─→ FillDetector.process_fill()
  └─→ State file I/O operations

Threads That Access State:
  ├─→ Main thread (heartbeat loop)
  ├─→ WebSocket thread (price updates, fills)
  ├─→ Fill processor thread (queue worker)
  └─→ Aggressive polling threads (order checks)
```

---

## 🔌 Callback Wiring

### WebSocket → GridBot

```python
# File: bot/strategy/gridbot.py

# Setup during initialization
self.ws_handler.setup_callbacks(
    on_price_update=self._on_price_update,
    on_fill=self.fill_detector.process_websocket_fill
)

# When price update arrives:
def _on_price_update(self, price: float):
    self.previous_price = self.current_price
    self.current_price = price
    self.last_price_update = time.time()
    
    # Update monitoring
    self.price_monitor.update(price)
    
    # Check for anomalies
    self.anomaly_detector.run_all_checks(
        current_price=self.current_price,
        previous_price=self.previous_price,
        last_ws_update=self.last_price_update
    )
```

---

### FillDetector → GridBot

```python
# File: bot/strategy/gridbot.py

# Wire during initialization
self.fill_detector.set_fill_callback(self._on_fill_processed)

# When fill is processed:
def _on_fill_processed(self, fill_data: Dict):
    # Determine if BUY or SELL
    side = fill_data.get('side', '').upper()
    
    if side == 'BUY':
        # Route to LONG handler
        self.long_handler.handle_buy_fill(fill_data)
    elif side == 'SELL':
        # Route to SHORT handler
        self.short_handler.handle_sell_fill(fill_data)
```

---

### OrderManager → FillDetector (Aggressive Polling)

```python
# File: bot/strategy/modules/order_manager.py

# Wire during initialization
self.order_mgr.set_fill_callback(self.fill_detector.process_websocket_fill)

# In aggressive polling thread:
def _aggressive_polling_thread(self, order_id, max_checks):
    for i in range(max_checks):
        order_data = self.api_client.get_order(order_id)
        
        if order_data.get('state') == 'filled':
            # Manually trigger fill processing
            self.fill_callback(order_data)
            break
        
        time.sleep(2)  # Check every 2 seconds
```

---

## 📦 Module Dependencies Map

```
GridCalculator
  └─→ No dependencies (pure logic)

PositionManager
  └─→ GridCalculator

FillDetector
  └─→ PositionManager (lock only)

DeltaClient
  └─→ No dependencies (REST API)

OrderManager
  ├─→ DeltaClient
  ├─→ GridCalculator
  └─→ PositionManager

Reconciliation
  ├─→ OrderManager
  ├─→ PositionManager
  └─→ GridCalculator

VolatilityHandler
  ├─→ GridCalculator
  ├─→ PositionManager
  └─→ OrderManager

WebSocketManager
  └─→ No dependencies (WebSocket client)

WebSocketHandler
  └─→ WebSocketManager

LongFillHandler / ShortFillHandler
  └─→ GridBot instance (all modules)

Monitoring Systems
  └─→ Observe all modules (no control)
```

---

## 🎯 Critical Design Principles

### 1. Single Responsibility Principle
Each module does ONE thing:
- GridCalculator: Math only
- PositionManager: State only
- OrderManager: Orders only
- FillDetector: Fill deduplication only

### 2. Dependency Inversion
- High-level modules (GridBot) depend on abstractions
- Low-level modules (DeltaClient) implement abstractions
- Dependencies flow inward

### 3. Thread Safety
- One lock to rule them all (PositionManager's lock)
- Queue-based processing (FillDetector)
- Atomic operations with lock held

### 4. Event-Driven Architecture
- Callbacks instead of polling
- Loose coupling between modules
- Easy to add new listeners

### 5. Fail-Safe Design
- REST API fallback if WebSocket fails
- Aggressive polling backup for fills
- State persistence for crash recovery
- Orphan detection on startup

---

## 🚨 Common Pitfalls

### ❌ DON'T: Change initialization order
```python
# WRONG - Will crash!
self.order_mgr = OrderManager(...)  # Needs PositionManager
self.position_mgr = PositionManager(...)  # Created after!
```

### ✅ DO: Follow dependency order
```python
# CORRECT
self.position_mgr = PositionManager(...)  # Create first
self.order_mgr = OrderManager(           # Use after
    position_manager=self.position_mgr
)
```

---

### ❌ DON'T: Modify state without lock
```python
# WRONG - Race condition!
self.position_mgr.open_tranches.append(new_position)
```

### ✅ DO: Use PositionManager methods (lock protected)
```python
# CORRECT
self.position_mgr.add_position(new_position)  # Lock held inside
```

---

### ❌ DON'T: Create circular dependencies
```python
# WRONG - Circular!
OrderManager → Reconciliation → OrderManager
```

### ✅ DO: Maintain dependency tree
```python
# CORRECT - Tree structure
GridCalculator ← PositionManager ← OrderManager ← Reconciliation
```

---

## 🎓 Understanding the Architecture

### Why This Design?

**Before (God Class):**
- 3,492 lines in one file
- All logic mixed together
- Hard to test
- Hard to understand
- Hard to extend

**After (Modular):**
- ~200 lines per module
- Single responsibility
- Easy to test
- Easy to understand
- Easy to extend

### Key Insight: Thin Orchestrator Pattern

```
GridBot (orchestrator) = Brain
  ↓
Modules (specialists) = Organs
  ↓
Each does one thing well
  ↓
Orchestrator coordinates them
```

Like a conductor with an orchestra:
- Conductor doesn't play instruments
- Conductor coordinates musicians
- Each musician is an expert at their instrument
- Together they create harmony

---

## 📚 Related Documentation

- **Complete System**: `BOT_STRUCTURE.md`
- **Monitoring Systems**: `BOT_ACTIONS_SYSTEM.md`
- **Safety Systems**: `AI_CRITICAL_RULES.md`
- **WebSocket**: `DEEP_WIRING_AUDIT_NOV9_2025.md`
- **Aggressive Polling**: Bug fix applied Nov 7, 2025

---

## ✅ Verification Checklist

Use this to verify architecture integrity:

- [ ] Modules initialized in dependency order
- [ ] All callbacks wired correctly
- [ ] State lock shared between PositionManager and FillDetector
- [ ] Monitoring systems connected to OrderManager
- [ ] WebSocket handler routes to correct callbacks
- [ ] Fill handlers receive GridBot instance
- [ ] Aggressive polling callback set on OrderManager
- [ ] MonitoringDataWriter receives bot instance
- [ ] No circular dependencies
- [ ] No global state (except config)

---

**Last Verified:** November 9, 2025  
**Architecture Version:** v2.0 (Refactored)  
**Status:** ✅ Production Ready
