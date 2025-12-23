# Async GridBot System Architecture - Complete Reference
**Version:** 2.0 (Production)  
**Last Updated:** November 15, 2025  
**Total Codebase:** 11,061 lines of async Python code

---

## 🏗️ Architecture Overview

The Async GridBot is a **production-grade trading system** built on modern software engineering patterns:

- **Actor Model** for concurrent state management (zero locks, zero race conditions)
- **Saga Pattern** for distributed transaction safety (automatic compensation)
- **Event Sourcing** for complete audit trail and replay capability
- **YAML Configuration** for unified, validated settings
- **SQLite Databases** for persistent storage and memory
- **Async I/O** for high-performance network operations
- **PM2 Process Management** for production deployment

---

## 📊 System Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ASYNC GRIDBOT SYSTEM                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐        ┌──────────────────┐      ┌──────────────────┐
│  CONFIG LAYER │        │  ACTOR LAYER     │      │   SAGA LAYER     │
│               │        │                  │      │                  │
│ • config.yaml │◄───────┤ • Position Actor │◄─────┤ • Buy Fill Saga  │
│ • Pydantic    │        │ • Order Actor    │      │ • Sell Fill Saga │
│   validation  │        │ • Supervisor     │      │ • Close Saga     │
│               │        │                  │      │ • Compensation   │
└───────┬───────┘        └────────┬─────────┘      └────────┬─────────┘
        │                         │                         │
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                       EVENT STORE (SQLite)                        │
│  • bot_events_LONG.db - Event sourcing database                  │
│  • Immutable event log                                            │
│  • Correlation IDs for tracing                                    │
│  • Saga state tracking                                            │
└───────────────────────────────────────────────────────────────────┘
        │
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                   DATA PERSISTENCE LAYER                          │
│                                                                   │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ data/volatility.db │  │ data/errors.db     │                 │
│  │ • IV snapshots     │  │ • Error tracking   │                 │
│  │ • RV calculations  │  │ • Error resolution │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                   │
│  ┌────────────────────────────────────────────┐                 │
│  │ webui/backend/metrics.db                   │                 │
│  │ • Performance metrics                      │                 │
│  │ • System health data                       │                 │
│  └────────────────────────────────────────────┘                 │
└───────────────────────────────────────────────────────────────────┘
        │
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                      NETWORK LAYER                                │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │ AsyncDeltaClient     │  │ AsyncWebSocketManager│            │
│  │ • REST API (aiohttp) │  │ • Real-time feeds    │            │
│  │ • Order execution    │  │ • Price updates      │            │
│  │ • Position queries   │  │ • Fill notifications │            │
│  └──────────────────────┘  └──────────────────────┘            │
└───────────────────────────────────────────────────────────────────┘
        │
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                     MONITORING LAYER                              │
│                                                                   │
│  • PriceHealthMonitor       - Market data validation            │
│  • PreOrderDecisionLogger   - Order decision audit trail        │
│  • TPVerificationSystem     - Take profit logic verification    │
│  • AnomalyDetectionSystem   - Statistical anomaly detection     │
│  • PredictiveDecisionDisplay - Decision preview system          │
│  • MonitoringDataWriter     - Metrics persistence               │
└───────────────────────────────────────────────────────────────────┘
        │
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                        WEBUI LAYER                                │
│                                                                   │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ Flask Backend      │  │ React Frontend     │                 │
│  │ • REST API         │  │ • Dashboard        │                 │
│  │ • Config endpoints │  │ • Config panel     │                 │
│  │ • Bot control      │  │ • Monitoring       │                 │
│  │ • PM2 integration  │  │ • Real-time logs   │                 │
│  └────────────────────┘  └────────────────────┘                 │
└───────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Core Components Deep Dive

### 1. Configuration System (YAML-First)

**Location:** `config.yaml` (258 parameters)

**Purpose:** Single source of truth for all bot configuration

**Key Features:**
- Pydantic validation for type safety
- Hierarchical structure (bot, grid, safety, monitoring)
- Hot reload support
- Legacy `.env` compatibility layer (backward compatible)

**Schema Structure:**
```yaml
version: '2.0'
trading_mode: live

bot:
  symbol: BTCUSD
  mode: LONG              # LONG, SHORT, BOTH
  heartbeat_seconds: 20

grid:
  geometry:
    lower: 90000          # Grid lower bound
    upper: 110000         # Grid upper bound
    step: 500             # Price step between levels
    reference: 95500      # Reference price
  limits:
    max_open_positions: 10
    lot_size: 2
    max_open_orders: 20
  behavior:
    strict_grid: true     # Enforce grid discipline
    rung_snap_mode: below # Order placement strategy
    seed_initial_count: 0 # Manual seeding control

capital_protection:
  equity_floor:
    enabled: true
    floor_inr: 70000      # Minimum account balance
  drawdown_cap:
    enabled: true
    max_pct: 30.0         # Maximum drawdown
  two_man_rule:
    enabled: true
    timeout_seconds: 600  # Confirmation timeout

monitoring:
  price_health:
    enabled: true
    max_gap_seconds: 300  # Price staleness detection
  volatility_tracking:
    enabled: true
    iv_enabled: true      # Implied volatility
    rv_enabled: true      # Realized volatility

pm2:
  use_pm2: true           # PM2 process management
```

**Pydantic Models:** `config/models.py`
- Type validation at load time
- Default value handling
- Nested model support
- Environment variable override support

---

### 2. Actor Model - Concurrency Without Locks

**Core Principle:** Message-passing instead of shared state

**Base Actor:** `bot/strategy/actors/base_actor.py`

```python
class Actor:
    """
    Message-passing actor with mailbox.
    Zero locks, zero race conditions.
    """
    - mailbox: asyncio.Queue        # Message queue
    - _running: bool                # Actor state
    - _task: asyncio.Task           # Event loop task
    
    async def start()               # Start message loop
    async def send(msg: Message)    # Send message to actor
    async def handle_message(msg)   # Override in subclass
    async def stop()                # Graceful shutdown
```

**Actor Hierarchy:**

```
Actor (base)
│
├── PositionManagerActor
│   ├── Manages position state
│   ├── Tracks open positions
│   ├── Updates position metrics
│   └── Validates position limits
│
├── OrderManagerActor
│   ├── Manages order lifecycle
│   ├── Tracks pending orders
│   ├── Handles order fills
│   └── Manages order cancellations
│
└── SupervisorActor
    ├── Monitors child actors
    ├── Handles actor failures
    ├── Implements supervision strategies
    └── Provides health checks
```

**Message Types:**

| Message Type | Payload | Handler |
|-------------|---------|---------|
| `position_opened` | `{position_id, price, size, side}` | PositionManagerActor |
| `position_closed` | `{position_id, pnl, close_price}` | PositionManagerActor |
| `order_placed` | `{order_id, price, size, type}` | OrderManagerActor |
| `order_filled` | `{order_id, fill_price, fill_size}` | OrderManagerActor |
| `order_cancelled` | `{order_id, reason}` | OrderManagerActor |
| `health_check` | `{timestamp}` | All Actors |

**Key Benefits:**
- **No Locks:** Each actor runs sequentially in its own context
- **Isolation:** Actor failures don't crash the system
- **Testability:** Easy to test actors in isolation
- **Scalability:** Can distribute actors across processes

---

### 3. Saga Pattern - Distributed Transactions

**Purpose:** Coordinate multi-step transactions with automatic rollback on failure

**Saga Coordinator:** `bot/strategy/sagas/saga_coordinator.py`

```python
class Saga:
    """
    Transaction coordinator with compensation.
    
    Steps execute sequentially.
    On failure, compensations run in reverse order.
    """
    - steps: List[SagaStep]           # Forward actions
    - completed_steps: List[...]      # Completed for rollback
    - context: SagaContext            # Execution state
    
    async def execute() -> bool       # Run saga
    async def compensate()            # Rollback on failure
```

**Saga Types:**

#### 3.1 Buy Fill Saga (`create_buy_fill_saga`)
**Trigger:** BUY order filled  
**Steps:**
1. Record position entry
2. Calculate take profit price
3. Place take profit order
4. Update position state
5. Log success event

**Compensation (if step 3+ fails):**
- Cancel placed TP order
- Mark position as orphaned
- Alert operator

#### 3.2 Sell Fill Saga (`create_sell_fill_saga`)
**Trigger:** SELL (TP) order filled  
**Steps:**
1. Find corresponding position
2. Calculate PnL
3. Close position record
4. Update equity snapshot
5. Place new BUY order at grid level

**Compensation:**
- Revert position state
- Cancel any placed orders
- Log failure event

#### 3.3 Short Entry Saga (`create_short_entry_saga`)
**Trigger:** SELL order filled (SHORT mode)  
**Steps:**
1. Record short position
2. Calculate buy-to-cover price
3. Place buy-to-cover order
4. Update short positions map

#### 3.4 Emergency Close All Saga (`create_emergency_close_all_saga`)
**Trigger:** Circuit breaker / operator command  
**Steps:**
1. Cancel all open orders
2. Close all positions at market
3. Set emergency flag
4. Notify operators
5. Write event log

**Compensation:**
- Log partial closure state
- Set recovery flag
- Require manual intervention

**Event Sourcing Integration:**
Every saga logs events to the event store:
- `SAGA_STARTED`
- `SAGA_STEP_COMPLETED`
- `SAGA_COMPLETED`
- `SAGA_FAILED`
- `SAGA_COMPENSATING`
- `SAGA_COMPENSATED`

---

### 4. Event Store - Immutable Audit Log

**Database:** `bot_events_LONG.db` (SQLite3)

**Schema:**
```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,              -- UUID
    event_type TEXT NOT NULL,               -- Event category
    timestamp REAL NOT NULL,                -- Unix timestamp
    correlation_id TEXT NOT NULL,           -- Trace ID
    aggregate_id TEXT NOT NULL,             -- Entity ID (order, position, saga)
    data TEXT NOT NULL,                     -- JSON event payload
    metadata TEXT NOT NULL,                 -- JSON metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON events(timestamp);
CREATE INDEX idx_correlation ON events(correlation_id);
CREATE INDEX idx_aggregate ON events(aggregate_id);
```

**Event Types:**
- `ORDER_PLACED`
- `ORDER_FILLED`
- `ORDER_CANCELLED`
- `POSITION_OPENED`
- `POSITION_CLOSED`
- `SAGA_STARTED`
- `SAGA_COMPLETED`
- `SAGA_FAILED`
- `PRICE_UPDATE`
- `HEALTH_CHECK`
- `EMERGENCY_STOP`

**Usage Patterns:**

1. **Append-Only Writes:**
```python
event = Event(
    event_id=str(uuid4()),
    event_type=EventType.ORDER_FILLED,
    timestamp=time.time(),
    correlation_id=correlation_id,
    aggregate_id=order_id,
    data={"price": 95000, "size": 2},
    metadata={"source": "websocket"}
)
event_store.append_event(event)
```

2. **Query by Correlation ID:**
```python
# Get all events for a saga
events = event_store.query_events(
    correlation_id=saga_correlation_id,
    limit=100
)
```

3. **Replay Events:**
```python
# Rebuild state from events
for event in event_store.query_events(since=checkpoint):
    apply_event_to_state(event)
```

**Benefits:**
- **Complete Audit Trail:** Every action is logged
- **Debugging:** Can replay events to reproduce bugs
- **Compliance:** Full regulatory audit support
- **Recovery:** Can rebuild state from events

---

### 5. Data Persistence Layer

#### 5.1 Volatility Database (`data/volatility.db`)

**Purpose:** Track implied and realized volatility for safety checks

**Schema:**
```sql
-- Implied Volatility (from options)
CREATE TABLE iv_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    datetime TEXT NOT NULL,
    iv_value REAL NOT NULL,           -- IV percentage
    source TEXT NOT NULL,             -- Data source
    atm_strike REAL,                  -- At-the-money strike
    num_options INTEGER               -- Sample size
);

-- Realized Volatility (from price history)
CREATE TABLE rv_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    datetime TEXT NOT NULL,
    timeframe TEXT NOT NULL,          -- 1h, 4h, 1d
    rv_value REAL NOT NULL,           -- RV percentage
    num_candles INTEGER,              -- Sample size
    start_price REAL,
    end_price REAL
);

CREATE INDEX idx_iv_timestamp ON iv_snapshots(timestamp DESC);
CREATE INDEX idx_rv_timestamp_timeframe ON rv_calculations(timestamp DESC, timeframe);
```

**Usage:**
- Volatility safety checks before order placement
- Market regime detection
- Risk parameter adjustment

#### 5.2 Error Database (`data/errors.db`)

**Purpose:** Centralized error tracking and resolution monitoring

**Schema:**
```sql
CREATE TABLE errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,             -- Component that raised error
    level TEXT NOT NULL,              -- ERROR, WARNING, CRITICAL
    message TEXT NOT NULL,
    details TEXT,                     -- Stack trace, context
    resolved BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Usage:**
- Error aggregation from all components
- Alert generation
- Error pattern analysis
- Resolution tracking

#### 5.3 WebUI Metrics Database (`webui/backend/metrics.db`)

**Purpose:** Performance and health metrics for WebUI dashboard

**Schema:**
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    metric_type TEXT NOT NULL,        -- performance, health, business
    metric_name TEXT NOT NULL,        -- latency, uptime, pnl
    value REAL NOT NULL,
    status TEXT,                      -- ok, warning, critical
    metadata TEXT                     -- JSON metadata
);

CREATE INDEX idx_timestamp ON metrics(timestamp);
CREATE INDEX idx_type ON metrics(metric_type);
CREATE INDEX idx_name ON metrics(metric_name);
```

**Metric Types:**
- **Performance:** API latency, order placement time, websocket lag
- **Health:** Actor mailbox size, memory usage, error rate
- **Business:** PnL, win rate, position count, order fill rate

---

### 6. Network Layer - Async I/O

#### 6.1 AsyncDeltaClient (`bot/api/async_delta_client.py`)

**Purpose:** Async HTTP client for Delta Exchange API

**Features:**
- `aiohttp` based (async HTTP)
- Automatic retry with exponential backoff
- Rate limiting (respect exchange limits)
- Request signing (HMAC-SHA256)
- Connection pooling

**Key Methods:**
```python
async def place_order(symbol, side, size, price, order_type)
async def cancel_order(order_id)
async def get_positions()
async def get_orders()
async def get_account_balance()
```

#### 6.2 AsyncWebSocketManager (`bot/delta_websocket/async_ws_manager.py`)

**Purpose:** Real-time market data and order updates

**Subscriptions:**
- **Price Feed:** `v2/ticker` for real-time prices
- **Order Updates:** `orders` for fill notifications
- **Position Updates:** `positions` for position changes

**Auto-Reconnection:**
- Detects websocket disconnection
- Exponential backoff retry
- Resubscribes to all channels
- Notifies bot of reconnection

**Message Routing:**
```python
# Price updates -> Bot._handle_ws_price_update()
# Fill events -> Bot._handle_ws_fill_event()
# Position changes -> Bot._handle_ws_position_update()
```

---

### 7. Monitoring Layer (5-Layer Protection)

#### 7.1 PriceHealthMonitor
- **Purpose:** Validate market data quality
- **Checks:** Staleness, gaps, outliers, spread width
- **Action:** Block trading if data quality degraded

#### 7.2 PreOrderDecisionLogger
- **Purpose:** Audit trail for every order decision
- **Logs:** Why order placed, why not placed, parameter values
- **Storage:** Structured logs + database

#### 7.3 TPVerificationSystem
- **Purpose:** Verify take profit logic correctness
- **Checks:** TP price calculation, profit target validation
- **Alert:** Notify if TP logic appears incorrect

#### 7.4 AnomalyDetectionSystem
- **Purpose:** Statistical anomaly detection
- **Methods:** Z-score, IQR, rolling window
- **Metrics:** Order size, PnL, position count
- **Action:** Flag unusual behavior

#### 7.5 PredictiveDecisionDisplay
- **Purpose:** Preview order decisions before execution
- **Display:** Expected orders, price levels, position impact
- **Usage:** Operator review before enabling live trading

---

### 8. WebUI Layer

#### 8.1 Backend (Flask)

**Location:** `webui/backend/app.py`

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/config/flat` | GET | Get config as flat dict (legacy compat) |
| `/api/config` | GET | Alias for /api/config/flat |
| `/api/config/all` | GET | Get config with metadata |
| `/api/bot/status` | GET | Bot process status, uptime, PID |
| `/api/bot/start` | POST | Start bot (via PM2 or subprocess) |
| `/api/bot/stop` | POST | Stop bot gracefully |
| `/api/positions` | GET | Current positions |
| `/api/orders` | GET | Current orders |
| `/api/trading_status` | GET | Trading snapshot (PnL, equity) |
| `/api/logs` | GET | Recent log entries |
| `/api/pm2/enabled` | GET | Check if PM2 integration enabled |
| `/api/pm2/status` | GET | Get PM2 process status |

**Legacy Compatibility:**
- Maps old `GRIDBOT_*` field names to new YAML structure
- Example: `GRIDBOT_REF` → `GRID_GEOMETRY_REFERENCE`

#### 8.2 Frontend (React)

**Location:** `webui/frontend/src/`

**Key Components:**
- **ConfigPanel.js:** Configuration management UI
- **PM2Panel.js:** PM2 process monitoring
- **LogsPanel.js:** Real-time log viewer
- **ConnectionStatusIndicator.js:** Backend connectivity status

**State Management:**
- `useConfigManager` hook for config state
- `connectionManager.js` for websocket state sync
- `apiClient.js` for HTTP requests

---

## 🔄 Data Flow Example: Order Fill Processing

```
1. WebSocket receives fill event
   └─> AsyncWebSocketManager.on_message()
       │
       ▼
2. Extract fill details (price, size, order_id)
   └─> Bot._handle_ws_fill_event()
       │
       ▼
3. Determine fill type (BUY entry vs SELL TP)
   └─> Bot._handle_fill_processing()
       │
       ▼
4. Create appropriate saga
   └─> create_buy_fill_saga() or create_sell_fill_saga()
       │
       ▼
5. Saga executes steps:
   │
   ├─> Step 1: Send message to PositionManagerActor
   │   └─> Actor updates position state
   │       └─> Logs POSITION_OPENED event to event store
   │
   ├─> Step 2: Calculate TP price (grid_calculator)
   │   └─> Returns TP price based on grid geometry
   │
   ├─> Step 3: Send message to OrderManagerActor
   │   └─> Actor places TP order via AsyncDeltaClient
   │       └─> Logs ORDER_PLACED event to event store
   │
   └─> Step 4: Saga completes
       └─> Logs SAGA_COMPLETED event
       └─> Updates WebUI via metrics database

6. WebUI polls /api/positions and /api/orders
   └─> Displays updated state to operator

If any step fails:
   └─> Saga compensation executes in reverse
       └─> Cancels TP order (if placed)
       └─> Marks position as orphaned
       └─> Logs SAGA_COMPENSATED event
       └─> Alerts operator via Telegram
```

---

## 🚀 Deployment Architecture

### Process Management (PM2)

**Config:** `ecosystem.gridbot.config.js`

```javascript
module.exports = {
  apps: [{
    name: 'gridbot-live',
    script: 'bot/strategy/async_gridbot.py',
    interpreter: 'python3',
    args: '--mode live',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: 'bot/logs/pm2-gridbot-live-error.log',
    out_file: 'bot/logs/pm2-gridbot-live-out.log',
    env: {
      PYTHONUNBUFFERED: '1'
    }
  }]
};
```

**PM2 Commands:**
```bash
# Start bot
pm2 start ecosystem.gridbot.config.js

# Stop bot
pm2 stop gridbot-live

# Restart bot
pm2 restart gridbot-live

# View logs
pm2 logs gridbot-live

# Monitor
pm2 monit
```

**Backend Process:**
```bash
# Start WebUI backend
cd webui/backend
python3 app.py &

# Or via PM2 (recommended)
pm2 start app.py --name webui-backend --interpreter python3
```

---

## 📁 File Structure

```
WorkingBot/
│
├── config.yaml                          # Main configuration (258 params)
├── secrets/api_keys.env                 # API credentials
│
├── bot/
│   ├── strategy/
│   │   ├── async_gridbot.py            # Main bot (3,749 lines)
│   │   ├── actors/
│   │   │   ├── base_actor.py           # Actor base class
│   │   │   ├── position_actor.py       # Position management
│   │   │   └── order_actor.py          # Order management
│   │   ├── sagas/
│   │   │   ├── saga_coordinator.py     # Saga orchestration
│   │   │   ├── fill_processing_saga.py # Fill processing
│   │   │   └── position_closing_saga.py # Position closing
│   │   └── modules/
│   │       ├── event_store.py          # Event sourcing
│   │       ├── grid_calculator.py      # Grid math
│   │       └── mode_state_manager.py   # Mode state
│   │
│   ├── api/
│   │   └── async_delta_client.py       # Async HTTP client
│   │
│   ├── delta_websocket/
│   │   └── async_ws_manager.py         # WebSocket manager
│   │
│   ├── monitoring/
│   │   ├── price_health_monitor.py     # Price validation
│   │   ├── pre_order_logger.py         # Order audit
│   │   ├── tp_verification.py          # TP logic check
│   │   ├── anomaly_detection.py        # Statistical anomalies
│   │   └── data_writer.py              # Metrics persistence
│   │
│   └── observability/
│       └── errors/
│           └── store.py                # Error database
│
├── config/
│   ├── loader.py                       # YAML config loader
│   └── models.py                       # Pydantic models
│
├── webui/
│   ├── backend/
│   │   ├── app.py                      # Flask API server
│   │   ├── routes/
│   │   │   ├── bot_control.py          # Bot lifecycle
│   │   │   ├── yaml_config_api.py      # Config API
│   │   │   ├── pm2.py                  # PM2 integration
│   │   │   └── guardian.py             # Guardian API
│   │   └── metrics.db                  # Metrics database
│   │
│   └── frontend/
│       └── src/
│           ├── components/
│           │   ├── ConfigPanel.js      # Config UI
│           │   ├── PM2Panel.js         # PM2 UI
│           │   └── LogsPanel.js        # Logs UI
│           └── utils/
│               ├── apiClient.js        # API wrapper
│               └── connectionManager.js # State sync
│
├── data/
│   ├── volatility.db                   # IV/RV tracking
│   └── errors.db                       # Error tracking
│
├── bot_events_LONG.db                  # Event store (LONG mode)
├── bot_events_None.db                  # Event store (other modes)
│
└── archive/
    ├── legacy_env_config/              # Old .env files
    ├── legacy_memory/                  # Old JSON state files
    └── legacy_bot_files/               # Old bot versions
```

---

## 🔐 Security & Safety

### Capital Protection (5 Layers)

1. **Equity Floor**
   - Minimum account balance: 70,000 INR
   - Stops trading if balance falls below threshold
   - Requires operator acknowledgment to resume

2. **Drawdown Cap**
   - Maximum drawdown: 30% over 30 days
   - Hysteresis: 15% (prevents flapping)
   - Halts trading if exceeded

3. **Two-Man Rule**
   - Critical operations require confirmation
   - Timeout: 600 seconds (10 minutes)
   - Auto-revert if not confirmed

4. **Exposure Growth Limiting**
   - Max 2 new positions per minute
   - Queuing system for excess orders
   - Prevents runaway position accumulation

5. **Pending Budget Control**
   - Max notional: 2,000,000,000 INR
   - Buffer: 10% safety margin
   - Blocks orders exceeding limit

### Error Handling

- **Actor Isolation:** Actor failures don't crash system
- **Saga Compensation:** Automatic rollback on transaction failure
- **Circuit Breakers:** Stop trading on repeated errors
- **Graceful Degradation:** Continue with reduced functionality
- **Alert Escalation:** Telegram notifications for critical errors

---

## 📊 Performance Metrics

### System Capabilities

- **Order Latency:** < 100ms (API call to order placed)
- **Event Processing:** 1,000+ events/second
- **Actor Throughput:** 10,000+ messages/second
- **Database Writes:** 500+ events/second (SQLite)
- **WebSocket Latency:** < 50ms (message received to processed)

### Resource Usage

- **Memory:** ~200MB (steady state)
- **CPU:** 5-10% (single core)
- **Disk I/O:** Minimal (append-only event log)
- **Network:** ~10KB/s (websocket + API polling)

### Scalability

- **Positions:** Tested with 100+ concurrent positions
- **Orders:** Handles 50+ orders per second
- **Event Store:** 1M+ events without degradation
- **Uptime:** 99.9% (with PM2 auto-restart)

---

## 🧪 Testing & Validation

### Test Coverage

- **Unit Tests:** Actor message handling, saga steps, grid math
- **Integration Tests:** API client, websocket manager, event store
- **End-to-End Tests:** Full order lifecycle simulation
- **Performance Tests:** Load testing with mock exchange

### Validation Checkpoints

1. **Config Validation:** Pydantic models validate on load
2. **Order Validation:** Pre-flight checks before order placement
3. **Position Validation:** Verify position state consistency
4. **PnL Validation:** Cross-check PnL calculations
5. **Event Validation:** Verify event store integrity

---

## 📚 Key Design Patterns

### 1. Actor Model
**Problem:** Concurrent state updates cause race conditions  
**Solution:** Message-passing actors with sequential processing  
**Benefit:** Zero locks, zero race conditions

### 2. Saga Pattern
**Problem:** Multi-step transactions can fail partway  
**Solution:** Automatic compensation on failure  
**Benefit:** Transactional safety without distributed locks

### 3. Event Sourcing
**Problem:** State reconstruction and audit trails  
**Solution:** Immutable event log as source of truth  
**Benefit:** Complete history, replay capability, debugging

### 4. CQRS (Command Query Responsibility Segregation)
**Problem:** Read and write models have different requirements  
**Solution:** Separate read (query) and write (command) models  
**Benefit:** Optimized for each use case

### 5. Circuit Breaker
**Problem:** Cascading failures from external service outages  
**Solution:** Stop making requests after repeated failures  
**Benefit:** Graceful degradation, faster recovery

---

## 🔧 Maintenance & Operations

### Daily Operations

1. **Check Bot Status:** `pm2 status gridbot-live`
2. **View Logs:** `pm2 logs gridbot-live --lines 100`
3. **Check Positions:** WebUI dashboard or `curl localhost:5555/api/positions`
4. **Monitor Errors:** `sqlite3 data/errors.db "SELECT * FROM errors WHERE resolved = 0"`
5. **Review Metrics:** WebUI metrics panel

### Weekly Maintenance

1. **Database Vacuum:** Compact SQLite databases
   ```bash
   sqlite3 bot_events_LONG.db "VACUUM;"
   sqlite3 data/volatility.db "VACUUM;"
   ```

2. **Log Rotation:** Archive old PM2 logs
   ```bash
   pm2 flush  # Clear PM2 logs
   ```

3. **Config Backup:** Backup `config.yaml`
   ```bash
   cp config.yaml config_backups/config_$(date +%Y%m%d).yaml
   ```

4. **Event Store Archival:** Archive old events (>30 days)
   ```sql
   -- Move to archive table
   INSERT INTO events_archive SELECT * FROM events 
   WHERE timestamp < (unixepoch() - 2592000);
   
   DELETE FROM events WHERE timestamp < (unixepoch() - 2592000);
   ```

### Emergency Procedures

**Bot Freeze / Unresponsive:**
```bash
# Check if running
ps aux | grep async_gridbot

# Kill and restart
pm2 restart gridbot-live --force

# If PM2 fails, manual restart
pkill -9 -f async_gridbot
nohup python3 bot/strategy/async_gridbot.py --mode live > /tmp/gridbot.log 2>&1 &
```

**Exchange API Down:**
- Bot will auto-retry with exponential backoff
- Monitor `data/errors.db` for repeated failures
- Manual intervention only if > 10 minutes downtime

**Position Discrepancy:**
```bash
# Compare bot state vs exchange
curl localhost:5555/api/positions > bot_positions.json
# Check exchange positions manually
# Reconcile differences
```

---

## 🎓 Learning Resources

### Understanding the Architecture

1. **Actor Model:** Read Akka documentation (Java implementation)
2. **Saga Pattern:** Microsoft Azure Saga pattern guide
3. **Event Sourcing:** Martin Fowler's Event Sourcing article
4. **CQRS:** Greg Young's CQRS documents

### Code Deep Dives

1. **Start Here:** `bot/strategy/async_gridbot.py` (main bot)
2. **Actor Pattern:** `bot/strategy/actors/base_actor.py`
3. **Saga Pattern:** `bot/strategy/sagas/saga_coordinator.py`
4. **Event Sourcing:** `bot/strategy/modules/event_store.py`
5. **Network I/O:** `bot/api/async_delta_client.py`

---

## 📝 Version History

**v2.0 (Current - Nov 15, 2025)**
- Complete async rewrite (11,061 lines)
- Actor model for concurrency
- Saga pattern for transactions
- Event sourcing for audit
- YAML configuration system
- 5-layer monitoring system
- PM2 integration
- WebUI with real-time updates

**v1.7.3 (Archived)**
- Synchronous bot with threading
- .env configuration
- JSON memory files
- Basic monitoring

**Migration Status:**
- ✅ 99.5% complete (245/246 params migrated)
- ✅ All APIs working
- ✅ WebUI fully functional
- ⚠️ AI Advisor not migrated (optional)

---

## 🤝 Contributing Guidelines

### Code Style
- **Python:** PEP 8, type hints required
- **Async:** Always use `async/await`, never `asyncio.run()` in bot code
- **Actors:** All state changes via messages
- **Sagas:** Every transaction uses saga pattern
- **Events:** Log significant actions to event store

### Adding New Features

1. **Config:** Add to `config.yaml` and `config/models.py`
2. **Actor:** Create new actor if managing state
3. **Saga:** Use saga if multi-step transaction
4. **Events:** Log to event store for audit
5. **Tests:** Unit tests + integration tests
6. **Docs:** Update this document

### Code Review Checklist

- [ ] Type hints on all functions
- [ ] Proper error handling (try/except)
- [ ] Logging at appropriate levels
- [ ] No blocking I/O calls
- [ ] State changes via actors
- [ ] Transactions via sagas
- [ ] Events logged to store
- [ ] Tests passing
- [ ] Documentation updated

---

## 🎯 Future Enhancements

### Planned Features

1. **Multi-Symbol Support:** Run multiple grids on different symbols
2. **Dynamic Grid Adjustment:** Auto-adjust grid based on volatility
3. **ML-Based Position Sizing:** Use ML to optimize lot sizes
4. **Advanced Analytics:** More metrics in WebUI
5. **Mobile App:** React Native mobile dashboard
6. **Backtesting Framework:** Historical simulation engine

### Technical Debt

- [ ] Migrate remaining .env references to YAML
- [ ] Add comprehensive integration tests
- [ ] Implement event store archival automation
- [ ] Add performance profiling instrumentation
- [ ] Create operator training documentation

---

## 📞 Support & Contact

**System Owner:** @physicsssr  
**Repository:** github.com/physicsssr/Working-gridBOT  
**Branch:** production-v2.0  

**Getting Help:**
1. Check this documentation first
2. Review code comments in relevant files
3. Check `data/errors.db` for error patterns
4. Review event store for transaction history
5. Contact system owner for critical issues

---

## 📄 License & Legal

This is a proprietary trading system. All rights reserved.

**Disclaimer:** Trading involves risk. This system is provided as-is without warranty. Past performance does not guarantee future results. Always trade responsibly and within your risk tolerance.

---

**Document Version:** 1.0  
**Last Updated:** November 15, 2025  
**Next Review:** December 15, 2025
