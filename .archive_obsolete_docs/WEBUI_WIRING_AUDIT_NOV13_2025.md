# 🔌 WebUI Wiring Audit - CRITICAL GAPS FOUND

**Date**: November 13, 2025  
**Status**: ⚠️ **3 CRITICAL GAPS IDENTIFIED**  
**Audit Scope**: WebUI → Backend → AsyncBot connectivity

---

## 📋 EXECUTIVE SUMMARY

### ✅ What Works
1. **PID File Management**: AsyncBot creates `reports/bot.pid` correctly ✅
2. **Bot Control**: WebUI can start/stop/status check bot ✅
3. **Configuration Read/Write**: WebUI reads/writes `grid_config.env` correctly ✅
4. **Orders API**: WebUI reads orders from Delta Exchange API ✅
5. **PnL Tracking**: WebUI reads PnL from CSV files (`pnl_history_YYYYMMDD.csv`) ✅
6. **WebSocket**: Log streaming works (tail_logs_and_emit) ✅

### ❌ What's Missing
1. **Positions File**: WebUI expects `bot/reports/positions.json` - **NOT CREATED BY ASYNCBOT** 🔴
2. **State File**: WebUI expects `bot/reports/state.json` - **NOT CREATED BY ASYNCBOT** 🔴
3. **Order Tags**: WebUI may not display client_order_id tags (GBOT_BUY_99000_timestamp) ⚠️

---

## 🔍 DETAILED AUDIT FINDINGS

### 1. Bot Control Wiring ✅ WORKING

**File**: `webui/backend/routes/bot_control.py`

**Endpoints**:
- `GET /api/bot/status` - Check bot running status
- `POST /api/bot/start` - Start bot via PM2 or bot_launcher.py
- `POST /api/bot/stop` - Stop bot gracefully (SIGTERM, 30s timeout)
- `POST /api/bot/restart` - Restart bot

**How It Works**:
1. WebUI checks for PM2 (via `should_use_pm2()`)
2. Fallback to PID file: `reports/bot.pid`
3. AsyncBot creates PID file in `bot/run.py` lines 502-508
4. Bot cleanup on shutdown (lines 626-632)

**Verification**:
```python
# bot/run.py lines 502-508
pid_file_path = Path("reports/bot.pid")
pid_file_path.parent.mkdir(exist_ok=True)
try:
    with open(pid_file_path, 'w') as f:
        f.write(str(os.getpid()))
    log.info(f"📝 Created PID file: {pid_file_path} (PID: {os.getpid()})")
```

**Status**: ✅ **WORKING** - PID file created correctly

---

### 2. Positions Data Flow ❌ BROKEN

**File**: `webui/backend/routes/positions.py`

**Endpoint**: `GET /api/positions`

**Expected Data Flow** (3 fallback strategies):
1. **Primary**: Delta Exchange API (with Greeks, real-time)
2. **Secondary**: Positions file (`bot/reports/positions.json`) ← **MISSING** 🔴
3. **Tertiary**: Guardian health data (`.guardian_health.json`)

**WebUI Expectation** (lines 52-53):
```python
POSITIONS_FILE = BASE_DIR / "bot" / "reports" / "positions.json"
STATE_FILE = BASE_DIR / "bot" / "reports" / "state.json"
```

**AsyncBot Reality**:
- ✅ PositionManagerActor manages state in memory (actor-based)
- ✅ Event sourcing to SQLite (`bot_events_LONG.db`)
- ❌ **DOES NOT** write `positions.json` file
- ❌ **DOES NOT** write `state.json` file

**Impact**:
- WebUI can get positions from Delta API (works)
- WebUI **CANNOT** get bot's internal state (pending orders, last order time, etc.)
- Reconciliation issues: WebUI shows exchange state, not bot state

**Files Checked**:
```bash
$ ls -la bot/reports/
pnl_history_*.csv           # ✅ PnL tracking files exist
volatility_history.json     # ✅ Volatility tracking exists
# positions.json             # ❌ MISSING
# state.json                 # ❌ MISSING
```

**Status**: 🔴 **CRITICAL GAP** - Bot state not accessible to WebUI

---

### 3. State Data Wiring ❌ BROKEN

**File**: `webui/backend/routes/positions.py`

**Endpoint**: `GET /api/state`

**Expected Data** (from `state.json`):
```json
{
  "open_tranches": [...],
  "pending_buy": {...},
  "pending_sell": {...},
  "last_buy_order_time": 1699876543,
  "last_sell_order_time": 1699876600,
  "total_positions_opened": 10,
  "total_positions_closed": 8
}
```

**WebUI Implementation** (lines 412-421):
```python
def _load_state_data():
    """Load bot runtime state from state file"""
    if not STATE_FILE.exists():
        return {}
    
    import json
    with open(STATE_FILE, 'r') as f:
        return json.load(f)
```

**AsyncBot Reality**:
- ✅ PositionManagerActor has complete state (lines 43-51 in position_actor.py):
  ```python
  self.state = {
      "open_tranches": [],
      "pending_buy": None,
      "pending_sell": None,
      "last_buy_order_time": 0,
      "last_sell_order_time": 0,
      "total_positions_opened": 0,
      "total_positions_closed": 0
  }
  ```
- ❌ State stored ONLY in memory + event store (SQLite)
- ❌ No JSON file export for WebUI consumption

**Impact**:
- WebUI cannot show pending orders
- WebUI cannot show last order timestamps
- WebUI cannot show position history stats
- Monitoring gaps: No visibility into bot's decision-making state

**Status**: 🔴 **CRITICAL GAP** - Internal bot state not exposed

---

### 4. Orders Data Wiring ⚠️ PARTIALLY WORKING

**File**: `webui/backend/routes/orders.py`

**Endpoint**: `GET /api/orders`

**How It Works**:
```python
# webui/backend/routes/orders.py lines 72-135
from bot.api.delta_client import DeltaClient

client = DeltaClient()
response = client.list_orders(product_id=..., state=...)

# Format orders with client_order_id
formatted_orders.append({
    'id': order.get('id'),
    'product_id': order.get('product_id'),
    'side': order.get('side'),
    'order_type': order.get('order_type'),
    # ... more fields ...
})
```

**AsyncBot Order Tagging**:
- ✅ Orders tagged with `GBOT_BUY_99000_1699876543` (order_actor.py lines 73-84)
- ✅ Tags sent as `client_order_id` (async_delta_client.py line 352)
- ⚠️ WebUI **MAY** display tags (depends on Delta API response format)

**Verification Needed**:
1. Check if Delta API returns `client_order_id` in `list_orders()`
2. Check if WebUI displays `client_order_id` field
3. Test with live orders to verify tag visibility

**Status**: ⚠️ **NEEDS VERIFICATION** - Tags may not be visible in WebUI

---

### 5. PnL Data Wiring ✅ WORKING

**File**: `webui/backend/routes/pnl.py`

**Endpoints**:
- `GET /api/pnl-history` - Historical PnL from CSV files
- `GET /api/pnl/summary` - Latest PnL from today's CSV

**Data Source**: `bot/reports/pnl_history_YYYYMMDD.csv`

**AsyncBot Reality**:
- ✅ PnL files created correctly
- ✅ WebUI reads from CSV files (no bot state needed)

**Status**: ✅ **WORKING**

---

### 6. Configuration Wiring ✅ WORKING

**File**: `webui/backend/routes/config.py`

**Endpoints**:
- `GET /api/config` - Get configuration with categorization
- `GET /api/config/all` - Get ALL parameters
- `POST /api/config/update` - Update multiple parameters
- `POST /api/config` - Update configuration (legacy)
- `GET /api/config/verify` - Verify configuration validity
- `POST /api/config/apply` - Apply configuration changes
- `POST /api/config/confirm-runtime` - Confirm runtime config

**Data Source**: `grid_config.env`

**AsyncBot Reality**:
- ✅ Bot reads from `grid_config.env` on startup
- ✅ All parameters wired correctly (100% coverage verified)

**Status**: ✅ **WORKING**

---

### 7. Monitoring Wiring ✅ WORKING

**File**: `webui/backend/routes/monitoring.py`

**Endpoints** (8 total):
- `GET /api/monitoring/status` - Bot monitoring status
- `GET /api/monitoring/price-health` - Price health check
- `GET /api/monitoring/pre-order-stats` - Pre-order statistics
- `GET /api/monitoring/tp-verification` - TP verification
- `GET /api/monitoring/anomalies` - Anomaly detection
- `GET /api/monitoring/predictive-map` - Predictive map
- `GET /api/monitoring/trading-condition` - Trading conditions

**Data Sources**:
- Monitoring snapshot files
- Delta Exchange API
- Log files

**Status**: ✅ **WORKING**

---

### 8. WebSocket Wiring ✅ WORKING (Partial)

**File**: `webui/backend/app.py`

**WebSocket Events**:
- `connect` - Client connected
- `disconnect` - Client disconnected
- `ping` - Heartbeat check
- `log_entry` - Real-time log streaming

**Implementation** (lines 286-344):
```python
def tail_logs_and_emit():
    """Background thread that tails bot log file and emits new lines via WebSocket"""
    # Tails bot.log and broadcasts via socketio.emit('log_entry', ...)

@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'Connected to GridBot WebUI'})
    # Start log tailer thread
```

**What Works**:
- ✅ Real-time log streaming
- ✅ Client connection management

**What's Missing**:
- ❌ Position updates not broadcast
- ❌ Order updates not broadcast
- ❌ Safety status not broadcast
- ❌ PnL updates not broadcast

**Status**: ⚠️ **PARTIAL** - Logs work, real-time data missing

---

## 🛠️ REQUIRED FIXES

### Fix #1: Add Positions File Export to AsyncBot 🔴 CRITICAL

**Goal**: AsyncBot writes `bot/reports/positions.json` for WebUI consumption

**Implementation Plan**:
1. Add `_save_positions_file()` method to PositionManagerActor
2. Call after position changes (add/remove)
3. Use 1-second debouncing (like state persistence)

**File**: `bot/strategy/actors/position_actor.py`

**Changes**:
```python
# Add after line 68 (in __init__)
self._positions_file = Path("bot/reports/positions.json")
self._positions_file.parent.mkdir(exist_ok=True)
self._last_positions_file_write = 0
self._min_positions_file_interval = 1.0  # 1 second

# Add new method (after line 230)
def _save_positions_file(self):
    """Save positions to JSON file for WebUI consumption"""
    now = time.time()
    if (now - self._last_positions_file_write) < self._min_positions_file_interval:
        return  # Debouncing
    
    try:
        positions_data = {
            "positions": [
                {
                    "position_id": pos["position_id"],
                    "entry_price": pos["entry_price"],
                    "tp_price": pos["tp_price"],
                    "size": pos["size"],
                    "status": "open",
                    "created_at": pos.get("created_at", now)
                }
                for pos in self.state["open_tranches"]
            ],
            "summary": {
                "total_positions": len(self.state["open_tranches"]),
                "total_opened": self.state["total_positions_opened"],
                "total_closed": self.state["total_positions_closed"],
            },
            "last_update": now
        }
        
        with open(self._positions_file, 'w') as f:
            json.dump(positions_data, f, indent=2)
        
        self._last_positions_file_write = now
        log.debug(f"📝 Saved positions file: {len(positions_data['positions'])} positions")
        
    except Exception as e:
        log.error(f"❌ Failed to save positions file: {e}")

# Call in _handle_add_position (after line 180)
self._save_positions_file()

# Call in _handle_remove_position (after line 220)
self._save_positions_file()
```

---

### Fix #2: Add State File Export to AsyncBot 🔴 CRITICAL

**Goal**: AsyncBot writes `bot/reports/state.json` for WebUI consumption

**File**: `bot/strategy/actors/position_actor.py`

**Changes**:
```python
# Add after line 71 (in __init__)
self._state_file = Path("bot/reports/state.json")
self._state_file.parent.mkdir(exist_ok=True)
self._last_state_file_write = 0
self._min_state_file_interval = 1.0  # 1 second

# Add new method (after _save_positions_file)
def _save_state_file(self):
    """Save state to JSON file for WebUI consumption"""
    now = time.time()
    if (now - self._last_state_file_write) < self._min_state_file_interval:
        return  # Debouncing
    
    try:
        state_data = {
            "open_positions": self.state["open_tranches"],
            "pending_buy": self.state["pending_buy"],
            "pending_sell": self.state["pending_sell"],
            "last_buy_order_time": self.state["last_buy_order_time"],
            "last_sell_order_time": self.state["last_sell_order_time"],
            "total_positions_opened": self.state["total_positions_opened"],
            "total_positions_closed": self.state["total_positions_closed"],
            "max_positions": self.max_positions,
            "last_update": now
        }
        
        with open(self._state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
        
        self._last_state_file_write = now
        log.debug(f"📝 Saved state file")
        
    except Exception as e:
        log.error(f"❌ Failed to save state file: {e}")

# Call in _handle_add_position, _handle_remove_position, 
# _handle_set_pending_buy, _handle_set_pending_sell
self._save_state_file()
```

---

### Fix #3: Verify Order Tags in WebUI ⚠️ NEEDS TESTING

**Goal**: Confirm WebUI displays `client_order_id` tags

**Testing Steps**:
1. Start bot with AsyncBot
2. Place orders (triggers tag generation)
3. Open WebUI → Orders page
4. Check if tags visible: `GBOT_BUY_99000_1699876543`

**If Tags Not Visible**:
Update `webui/backend/routes/orders.py` line 105:
```python
formatted_orders.append({
    'id': order.get('id'),
    'client_order_id': order.get('client_order_id'),  # ADD THIS LINE
    'product_id': order.get('product_id'),
    # ... rest of fields ...
})
```

---

### Fix #4: Enhance WebSocket Real-Time Updates ⚠️ ENHANCEMENT

**Goal**: Broadcast bot state changes via WebSocket

**Implementation Plan**:
1. Create `emit_bot_update()` helper in AsyncGridBot
2. Broadcast after position/order changes
3. Frontend subscribes to `bot_update` event

**File**: `bot/strategy/async_gridbot.py`

**Changes**:
```python
# Add method (after line 850)
def _emit_webui_update(self, event_type: str, data: Dict):
    """Broadcast bot state changes to WebUI via WebSocket"""
    try:
        from webui.backend.app import socketio
        socketio.emit('bot_update', {
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        })
    except Exception as e:
        # Fail silently if WebUI not running
        pass

# Call after position changes
self._emit_webui_update('position_added', {...})
self._emit_webui_update('position_closed', {...})
self._emit_webui_update('order_placed', {...})
```

---

## 📊 WIRING MATRIX

| Component | WebUI Endpoint | AsyncBot Source | Status |
|-----------|---------------|-----------------|--------|
| Bot Status | `/api/bot/status` | `reports/bot.pid` | ✅ Working |
| Positions | `/api/positions` | Delta API | ✅ Working |
| Positions (Internal) | `/api/positions` | `bot/reports/positions.json` | 🔴 **MISSING** |
| State | `/api/state` | `bot/reports/state.json` | 🔴 **MISSING** |
| Orders | `/api/orders` | Delta API | ✅ Working |
| Order Tags | `/api/orders` | `client_order_id` | ⚠️ Needs Verification |
| PnL | `/api/pnl-history` | CSV files | ✅ Working |
| Config | `/api/config` | `grid_config.env` | ✅ Working |
| Monitoring | `/api/monitoring/*` | Snapshots | ✅ Working |
| Logs | WebSocket `log_entry` | `bot.log` | ✅ Working |
| Real-time Data | WebSocket `bot_update` | N/A | ⚠️ Not Implemented |

---

## 🎯 PRIORITY ACTION ITEMS

### Priority 1: Critical Gaps (MUST FIX BEFORE PRODUCTION) 🔴
1. ✅ **Add positions.json export** to PositionManagerActor
2. ✅ **Add state.json export** to PositionManagerActor
3. ⚠️ **Test with running bot** to verify files created

### Priority 2: Verification (SHOULD TEST) ⚠️
4. ⚠️ Verify order tags visible in WebUI
5. ⚠️ Test bot start/stop from WebUI
6. ⚠️ Test config updates propagate to bot

### Priority 3: Enhancement (NICE TO HAVE) 💡
7. 💡 Add WebSocket real-time updates
8. 💡 Add safety status broadcasting
9. 💡 Add PnL update notifications

---

## ✅ VERIFICATION CHECKLIST

After implementing fixes, verify:

- [ ] Start bot → Check `bot/reports/positions.json` exists
- [ ] Start bot → Check `bot/reports/state.json` exists
- [ ] Add position → Verify positions.json updates
- [ ] Close position → Verify positions.json updates
- [ ] WebUI `/api/positions` → Shows bot state (not just exchange)
- [ ] WebUI `/api/state` → Shows pending orders
- [ ] WebUI Orders page → Shows client_order_id tags
- [ ] WebUI Config page → Update param → Bot reloads
- [ ] WebSocket → Real-time log streaming works
- [ ] Bot stop → PID file removed

---

## 📝 NOTES

**Why AsyncBot Doesn't Create These Files**:
- AsyncBot uses actor-based architecture with event sourcing
- State stored in memory (PositionManagerActor.state) + SQLite (event store)
- Legacy bots used JSON files for state persistence
- WebUI still expects legacy file format

**Migration Path**:
1. **Short-term**: Add JSON file export (this fix)
2. **Medium-term**: WebUI reads from event store directly
3. **Long-term**: WebUI uses AsyncBot's actor API (message passing)

**Production Impact**:
- Without these files, WebUI shows **exchange state** (what's on Delta)
- Bot's **internal state** (pending orders, cooldown, safety) is invisible
- Reconciliation and debugging become difficult

---

**Generated**: November 13, 2025 (00:20 AM)  
**Author**: GridBot WebUI Audit Team  
**Next Steps**: Implement Fix #1 and Fix #2 immediately

