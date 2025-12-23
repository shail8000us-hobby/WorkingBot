# AI_CONTEXT Architecture Addendum - November 20, 2025

**This document supplements AI_CONTEXT.md with detailed architecture information**

---

## 🚀 STARTUP SEQUENCE (CORRECT ORDER)

### **Production Startup:**
```bash
# 1. Start Guardian Bot (if not running)
python3 -m bot.guardian.guardian_bot

# 2. Run Recovery Engine (if needed - startup recovery)
python3 -m bot.strategy.recovery.recovery_runner

# 3. Start Reconciliation Engine (continuous monitoring)
python3 -m bot.strategy.reconciliation.reconciliation_runner &

# 4. Start Main Trading Bot
python3 -m bot.strategy.async_gridbot
```

### **Why This Order:**
1. **Guardian First** - Provides GO/STOP signals, must be running
2. **Recovery Second** - Recovers missed grids BEFORE bot starts trading
3. **Reconciliation Third** - Monitors for discrepancies while bot runs
4. **Bot Last** - Starts with clean state, skips recovered grids

---

## 📊 DATA FLOW DIAGRAMS

### **1. Trading Flow:**
```
Exchange (WebSocket)
    ↓
UnifiedAPIClient.ws_manager
    ↓
async_gridbot._handle_ticker_update()
    ├→ Update price cache
    ├→ Check Guardian status
    ├→ Comprehensive safety checks
    └→ Place order (if conditions met)
        ↓
    OrderActor (via message)
        ↓
    UnifiedAPIClient.rest_client
        ↓
    Exchange (REST API)
```

### **2. Fill Processing Flow:**
```
Exchange (WebSocket fill notification)
    ↓
async_gridbot._handle_user_trades()
    ↓
Saga Pattern (transactional)
    ├→ BuyFillSaga / SellFillSaga
    ├→ Update PositionActor
    ├→ Place TP order via OrderActor
    ├→ Event Store (audit log)
    └→ Compensation on failure
```

### **3. Recovery Flow:**
```
recovery_runner.py (startup)
    ↓
UnifiedAPIClient (REST)
    ↓
Query Exchange (positions, orders, price)
    ↓
Detect missed grids (MAX 3)
    ↓
Place market orders
    ↓
Write recovery_state.json
    {
      "recovery_active": false,
      "recovered_grids": [89000, 88500],
      "timestamp": 1700456789
    }
    ↓
async_gridbot.py reads state
    ↓
Skips recovered grids in normal trading
```

### **4. Reconciliation Flow:**
```
reconciliation_runner.py (every 5 min)
    ↓
UnifiedAPIClient (REST)
    ↓
Load bot_state.json
Query Exchange (truth)
    ↓
Detect discrepancies:
    ├→ Missed fills
    ├→ Unprotected positions
    ├→ Orphaned orders
    └→ State corruption
    ↓
Generate actions
    ↓
Write action_queue.json
    [{
      "type": "process_missed_fill",
      "order_id": "123456",
      "priority": "high"
    }]
    ↓
async_gridbot._reconciliation_action_processor()
    ↓
Execute actions (every 10 seconds)
    ↓
Mark as completed/failed
```

---

## 🔧 KEY COMPONENTS DEEP DIVE

### **UnifiedAPIClient**

**Purpose:** Single API layer for all systems

**Architecture:**
```python
class UnifiedAPIClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool,
        enable_websocket: bool,  # Optional!
        symbol: Optional[str] = None,
        product_id: Optional[int] = None
    ):
        # REST client (always)
        self.rest_client = AsyncDeltaClient(...)
        
        # WebSocket (optional)
        if enable_websocket:
            self.ws_manager = AsyncWebSocketManager(...)
        
        # Fallback state
        self.rest_fallback_active = False
        self.last_price_update = 0
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(...)
        
        # Rate limiter
        self.rate_limiter = RateLimiter(...)
```

**Key Methods:**
- `get_current_price()` - WebSocket with REST fallback
- `place_order()` - Always REST
- `list_orders()` - Always REST
- `get_positions()` - Always REST
- `update_price_from_websocket()` - Update price cache
- `get_health_status()` - Health monitoring

**Fallback Logic:**
```python
async def get_current_price(self) -> float:
    # If WebSocket active and price fresh (<10s old)
    if self.ws_active and not self._is_price_stale():
        return self.current_price
    
    # Otherwise, fall back to REST
    return await self._get_price_from_rest()
```

**Circuit Breaker:**
- Closed: Normal operation
- Open: After 5 failures, blocks for 60s
- Half-Open: After timeout, tries one request
- Auto-recovery: Returns to closed on success

**Rate Limiter:**
- Max 10 requests per second
- Automatic queuing
- Transparent to caller

---

### **Recovery Engine**

**File:** `bot/strategy/recovery/recovery_runner.py`

**When to Run:**
- Bot startup after downtime
- Price moved past grid levels
- Missed grids need recovery

**Process:**
1. Load config and API credentials
2. Create UnifiedAPIClient (REST only)
3. Query exchange for current state
4. Detect missed grids (compare price to grid levels)
5. Place market orders (MAX 3)
6. Write recovery_state.json
7. Exit

**Safety Limits:**
- MAX 3 grids recovered per run
- Prevents over-trading
- Manual intervention required for more

**Output File:**
```json
{
  "recovery_active": false,
  "recovered_grids": [89000.0, 88500.0],
  "timestamp": 1700456789.123,
  "last_recovery": 1700456789.123,
  "grids_recovered": 2
}
```

**Bot Integration:**
- Bot reads recovery_state.json at startup
- Skips recovered grids in normal trading
- Logs: "Skipping grid $89,000 - already recovered"

---

### **Reconciliation Engine**

**File:** `bot/strategy/reconciliation/reconciliation_runner.py`

**When to Run:**
- Continuously (every 5 minutes)
- Runs alongside bot
- Independent process

**Detects 4 Types:**

1. **Missed Fills:**
   - Bot thinks order is pending
   - Exchange says order is filled
   - Action: process_missed_fill

2. **Unprotected Positions:**
   - Position has no TP order
   - TP order not found on exchange
   - Action: place_emergency_tp

3. **Orphaned Orders:**
   - Order on exchange
   - Bot doesn't track it
   - Action: cancel_orphaned_order

4. **State Corruption:**
   - Invalid position data (e.g., entry_price = None)
   - Action: flag_corrupted_state

**Process:**
1. Load bot_state.json
2. Query exchange for truth
3. Compare and detect discrepancies
4. Generate correction actions
5. Write action_queue.json
6. Update reconciliation state
7. Wait 5 minutes, repeat

**Output Files:**

`action_queue.json`:
```json
{
  "actions": [
    {
      "id": "action_1700456789",
      "type": "process_missed_fill",
      "order_id": "123456",
      "side": "buy",
      "fill_price": 88500.0,
      "priority": "high",
      "status": "pending"
    }
  ],
  "updated_at": 1700456789.123
}
```

`state.json`:
```json
{
  "last_check_time": 1700456789.123,
  "checks_performed": 12,
  "discrepancies_found": 2,
  "actions_generated": 2,
  "status": "healthy"
}
```

**Bot Integration:**
- Bot has `_reconciliation_action_processor()` task
- Reads action_queue.json every 10 seconds
- Executes pending actions
- Marks as completed/failed
- Updates action queue

---

## 🔍 DEBUGGING GUIDE

### **Check System Health:**
```bash
# 1. Check all processes running
ps aux | grep -E "async_gridbot|recovery_runner|reconciliation_runner|guardian_bot"

# 2. Check bot state
cat data/bot_state.json | jq .

# 3. Check recovery state
cat data/recovery/recovery_state.json | jq .

# 4. Check reconciliation state
cat data/reconciliation/state.json | jq .
cat data/reconciliation/action_queue.json | jq .

# 5. Check Guardian signal
cat data/guardian_signal.json | jq .

# 6. Check API health
# (via bot logs or WebUI)
```

### **Common Issues:**

**1. Bot won't start:**
- Check Guardian is running: `ps aux | grep guardian_bot`
- Check Guardian signal: `cat data/guardian_signal.json`
- Check API credentials: `cat secrets/api_keys.env`
- Check WebSocket connection in logs

**2. Recovery not working:**
- Run recovery_runner.py BEFORE bot
- Check recovery_state.json exists
- Check bot logs for "skipping recovered grids"
- Check recovery_runner.py logs

**3. Reconciliation not working:**
- Check reconciliation_runner.py is running
- Check action_queue.json for pending actions
- Check bot logs for "Processing reconciliation action"
- Check reconciliation state.json

**4. WebSocket issues:**
- UnifiedAPIClient automatically falls back to REST
- Check logs for "REST fallback active"
- Check circuit breaker state
- Check price age in health status

**5. Price stale warnings:**
- Check WebSocket connection
- Check `api_client.update_price_from_websocket()` is called
- Check `_handle_ticker_update()` updates price cache
- Check fallback to REST is working

---

## 📋 FILE LOCATIONS

### **Core Bot:**
- `bot/strategy/async_gridbot.py` - Main trading bot
- `bot/strategy/actors/` - Actor system
- `bot/strategy/sagas/` - Saga pattern
- `bot/strategy/modules/` - Support modules

### **Standalone Systems:**
- `bot/strategy/recovery/recovery_runner.py` - Recovery engine
- `bot/strategy/reconciliation/reconciliation_runner.py` - Reconciliation engine
- `bot/api/unified_api_client.py` - Unified API layer

### **Data Files:**
- `data/bot_state.json` - Bot state
- `data/recovery/recovery_state.json` - Recovery state
- `data/reconciliation/state.json` - Reconciliation state
- `data/reconciliation/action_queue.json` - Action queue
- `data/guardian_signal.json` - Guardian GO/STOP signal

### **Configuration:**
- `config.yaml` - SINGLE SOURCE OF TRUTH
- `secrets/api_keys.env` - API credentials
- `config/` - Pydantic models and loader

---

## ✅ PRODUCTION READINESS CHECKLIST

### **Before Deployment:**
- [ ] Guardian bot running
- [ ] config.yaml configured correctly
- [ ] API credentials in secrets/api_keys.env
- [ ] Run recovery_runner.py if needed
- [ ] Start reconciliation_runner.py
- [ ] Start async_gridbot.py
- [ ] Check WebUI accessible (port 5555)
- [ ] Verify Guardian signal is GO
- [ ] Verify initial order placed
- [ ] Monitor logs for errors

### **During Operation:**
- [ ] Monitor Guardian status
- [ ] Monitor reconciliation checks
- [ ] Monitor action queue
- [ ] Check for price stale warnings
- [ ] Check circuit breaker state
- [ ] Monitor fill processing
- [ ] Check position protection (TPs)

---

**Created:** November 20, 2025, 2:35 AM  
**Status:** ✅ **COMPREHENSIVE ARCHITECTURE DOCUMENTATION**
