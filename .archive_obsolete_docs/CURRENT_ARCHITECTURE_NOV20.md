# Current Architecture - November 20, 2025

**Status:** ✅ **PRODUCTION-READY**

---

## 🏗️ **System Architecture**

### **Core Trading Bot:**
```
async_gridbot.py (3,530 lines)
├── UnifiedAPIClient (WebSocket + REST)
├── Actor System (Position + Order)
├── Saga Pattern (Transactional fills)
├── Event Store (Audit trail)
├── Grid Calculator
├── Guardian Integration
└── Monitoring Systems
```

### **Standalone Recovery Engine:**
```
recovery_runner.py (320 lines)
├── UnifiedAPIClient (REST only)
├── Detects missed grids
├── Places recovery orders (MAX 3)
├── Writes to recovery_state.json
└── Runs BEFORE bot starts
```

### **Standalone Reconciliation Engine:**
```
reconciliation_runner.py (489 lines)
├── UnifiedAPIClient (REST only)
├── Detects 4 types of discrepancies:
│   ├── Missed fills
│   ├── Unprotected positions
│   ├── Orphaned orders
│   └── State corruption
├── Generates correction actions
├── Writes to action_queue.json
└── Bot reads and executes actions
```

### **Unified API Layer:**
```
unified_api_client.py (468 lines)
├── WebSocket (optional)
├── REST API (always)
├── Automatic fallback
├── Circuit breaker
├── Rate limiter
└── Shared by ALL systems
```

---

## 📊 **Data Flow**

### **Trading Flow:**
```
Exchange
    ↓ (WebSocket)
UnifiedAPIClient
    ↓
async_gridbot.py
    ├→ Actor System (state)
    ├→ Saga Pattern (fills)
    └→ Event Store (audit)
```

### **Recovery Flow:**
```
recovery_runner.py
    ↓
UnifiedAPIClient (REST)
    ↓
Exchange (query state)
    ↓
recovery_state.json
    ↓
async_gridbot.py (reads state, skips recovered grids)
```

### **Reconciliation Flow:**
```
reconciliation_runner.py (every 5 min)
    ↓
UnifiedAPIClient (REST)
    ↓
Exchange (query truth)
    ↓
Detect discrepancies
    ↓
action_queue.json
    ↓
async_gridbot.py (reads queue, executes actions)
```

---

## 🔧 **Key Components**

### **1. UnifiedAPIClient**
**Purpose:** Single API layer for all systems

**Features:**
- Optional WebSocket (for real-time data)
- Always-available REST API
- Automatic fallback (WebSocket → REST)
- Circuit breaker (5 failures = open, 60s timeout)
- Rate limiter (10 requests/second)
- Health monitoring

**Usage:**
```python
# Bot (WebSocket + REST)
client = UnifiedAPIClient(
    api_key=key,
    api_secret=secret,
    testnet=testnet,
    enable_websocket=True,
    symbol="BTCUSD",
    product_id=27
)

# Recovery/Reconciliation (REST only)
client = UnifiedAPIClient(
    api_key=key,
    api_secret=secret,
    testnet=testnet,
    enable_websocket=False
)
```

---

### **2. Recovery Engine (Standalone)**
**Purpose:** Recover missed grids at startup

**Process:**
1. Run BEFORE bot starts
2. Detect missed grids (MAX 3)
3. Place market orders
4. Write to `recovery_state.json`
5. Bot reads state and skips recovered grids

**Command:**
```bash
python3 -m bot.strategy.recovery.recovery_runner
```

**State File:**
```json
{
  "recovery_active": false,
  "recovered_grids": [89000.0, 88500.0],
  "timestamp": 1700456789.123,
  "last_recovery": 1700456789.123
}
```

---

### **3. Reconciliation Engine (Standalone)**
**Purpose:** Detect and correct discrepancies

**Process:**
1. Run continuously (every 5 minutes)
2. Query bot state from `data/bot_state.json`
3. Query exchange for truth
4. Detect discrepancies
5. Generate correction actions
6. Write to `action_queue.json`
7. Bot reads queue and executes actions

**Command:**
```bash
python3 -m bot.strategy.reconciliation.reconciliation_runner
```

**Detects:**
- Missed fills (bot thinks pending, exchange says filled)
- Unprotected positions (positions without TP orders)
- Orphaned orders (orders on exchange not tracked by bot)
- State corruption (invalid position data)

**Action Queue:**
```json
{
  "actions": [
    {
      "id": "action_1700456789",
      "type": "process_missed_fill",
      "order_id": "123456",
      "side": "buy",
      "fill_price": 88500.0,
      "fill_size": 1,
      "priority": "high",
      "status": "pending"
    }
  ]
}
```

---

### **4. Actor System**
**Purpose:** Zero-lock state management

**Actors:**
- `PositionManagerActor` - Manages open positions
- `OrderManagerActor` - Manages orders

**Pattern:**
- Message-based communication
- No locks/mutexes
- Async message processing
- State isolation

---

### **5. Saga Pattern**
**Purpose:** Transactional fill processing

**Sagas:**
- `BuyFillSaga` - Process LONG entry fills
- `SellFillSaga` - Process LONG TP fills
- `ShortEntrySaga` - Process SHORT entry fills
- `ShortTPSaga` - Process SHORT TP fills
- `EmergencyCloseAllSaga` - Emergency position closure

**Features:**
- Automatic compensation on failure
- State persistence
- Retry logic
- Audit trail

---

## 📁 **File Structure**

```
bot/
├── api/
│   ├── async_delta_client.py (legacy, still used by OrderActor)
│   └── unified_api_client.py ✨ (NEW - shared by all)
│
├── strategy/
│   ├── async_gridbot.py (3,530 lines - main bot)
│   │
│   ├── actors/
│   │   ├── position_actor.py
│   │   └── order_actor.py
│   │
│   ├── sagas/
│   │   ├── fill_processing_saga.py
│   │   └── position_closing_saga.py
│   │
│   ├── recovery/ ✨ (NEW - standalone)
│   │   └── recovery_runner.py (320 lines)
│   │
│   └── reconciliation/ ✨ (NEW - standalone)
│       └── reconciliation_runner.py (489 lines)
│
└── monitoring/
    └── (various monitoring systems)

data/
├── bot_state.json (bot state)
├── recovery/
│   └── recovery_state.json ✨ (NEW)
└── reconciliation/ ✨ (NEW)
    ├── state.json
    └── action_queue.json
```

---

## 🚀 **Startup Sequence**

### **Correct Order:**
```bash
# 1. Start Guardian (if not running)
python3 -m bot.guardian.guardian_bot

# 2. Run Recovery (if needed)
python3 -m bot.strategy.recovery.recovery_runner

# 3. Start Reconciliation Engine
python3 -m bot.strategy.reconciliation.reconciliation_runner

# 4. Start Main Bot
python3 -m bot.strategy.async_gridbot
```

### **Bot Startup Process:**
1. Initialize UnifiedAPIClient (WebSocket + REST)
2. Initialize Actors (Position + Order)
3. Initialize Saga Orchestrator
4. Connect WebSocket
5. Subscribe to channels
6. Check Guardian status
7. Load recovered grids (skip in normal trading)
8. Place initial order
9. Start async tasks:
   - WebSocket message loop
   - Heartbeat loop
   - Monitoring loop
   - Health check loop
   - Reconciliation action processor ✨ (NEW)
   - REST fallback monitor
   - Watchdog loop
   - Safety gatekeeper
   - Guardian health monitor

---

## 🔍 **Debugging Guide**

### **Check System Health:**
```bash
# Check if all systems are running
ps aux | grep -E "async_gridbot|recovery_runner|reconciliation_runner|guardian_bot"

# Check bot state
cat data/bot_state.json

# Check recovery state
cat data/recovery/recovery_state.json

# Check reconciliation state
cat data/reconciliation/state.json
cat data/reconciliation/action_queue.json

# Check Guardian signal
cat data/guardian_signal.json
```

### **Common Issues:**

**1. Bot won't start:**
- Check Guardian is running
- Check Guardian signal is "GO"
- Check API credentials
- Check WebSocket connection

**2. Recovery not working:**
- Run recovery_runner.py BEFORE bot
- Check recovery_state.json exists
- Check bot logs for "skipping recovered grids"

**3. Reconciliation not working:**
- Check reconciliation_runner.py is running
- Check action_queue.json for pending actions
- Check bot logs for "Processing reconciliation action"

**4. WebSocket issues:**
- UnifiedAPIClient automatically falls back to REST
- Check logs for "REST fallback active"
- Circuit breaker may be open (check health status)

---

## 📊 **Monitoring**

### **Bot Metrics:**
- Fills processed
- Sagas completed/failed
- Open positions
- Pending orders
- Current price
- Guardian status

### **API Health:**
```python
health = api_client.get_health_status()
# Returns:
{
    'websocket': {
        'enabled': True,
        'active': True,
        'connected': True,
        'price_age': 2.5
    },
    'rest': {
        'active': True,
        'fallback_active': False,
        'circuit_breaker': {
            'state': 'closed',
            'failures': 0
        }
    }
}
```

### **Recovery Metrics:**
- Last recovery time
- Recovered grids count
- Recovery active status

### **Reconciliation Metrics:**
- Last check time
- Checks performed
- Discrepancies found
- Actions generated
- Pending actions count

---

## 🎯 **Key Benefits**

### **1. Clean Separation:**
- Recovery = Standalone (runs before bot)
- Reconciliation = Standalone (runs alongside bot)
- Bot = Pure trading logic

### **2. No Code Duplication:**
- All systems use UnifiedAPIClient
- Shared circuit breaker
- Shared rate limiter

### **3. Better Reliability:**
- Recovery crash ≠ Bot crash
- Reconciliation crash ≠ Bot crash
- Automatic fallback (WebSocket → REST)
- Circuit breaker prevents cascading failures

### **4. Easier Maintenance:**
- Update once, affects all systems
- Fix bugs once
- Add features once
- Clear boundaries

---

## 📚 **Documentation Files**

- `RECONCILIATION_ENGINE_COMPLETE.md` - Reconciliation system
- `OPTION_B_COMPLETE.md` - Recovery system
- `UNIFIED_API_LAYER_COMPLETE.md` - API layer
- `FINAL_CLEANUP_COMPLETE.md` - Code cleanup
- `logic.md` - Trading logic specification

---

**Created:** November 20, 2025, 2:25 AM  
**Status:** ✅ **PRODUCTION-READY**
