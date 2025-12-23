# AsyncBot Integration Audit - November 13, 2025

## Executive Summary

**Status**: 🟡 PARTIAL INTEGRATION - Async bot missing critical ecosystem connections

This audit compares how the old threaded GridBot integrates with the full ecosystem (Guardian, Heartbeat, PM2, monitoring systems) versus the new AsyncBot.

**Key Findings**:
1. ✅ **Core Architecture**: AsyncBot properly migrated with Actor pattern + Saga
2. ❌ **Guardian Integration**: Missing - No Guardian-compatible state files
3. ❌ **External Monitoring**: Missing - No continuous heartbeat file updates
4. ✅ **PM2 Configuration**: Present but needs verification
5. 🟡 **Log Format**: Different - AsyncBot logs less detailed than old bot
6. ❌ **Monitoring Systems**: Missing - 5-layer monitoring not implemented

---

## 1. File Import & Dependency Audit

### Old GridBot Imports (bot/strategy/gridbot.py)

```python
# Core modules
from bot.strategy.modules import (
    GridCalculator,           # ✅ AsyncBot has equivalent
    WebSocketHandler,         # ✅ AsyncBot uses AsyncWebSocketManager
    FillDetector,             # ✅ AsyncBot has fill processing saga
    PositionManager,          # ✅ AsyncBot has PositionManagerActor
    OrderManager,             # ✅ AsyncBot has OrderManagerActor
    Reconciliation,           # ✅ AsyncBot has _reconciliation_loop()
    VolatilityHandler         # ❌ AsyncBot MISSING
)

# Fill handlers
from bot.strategy.handlers import LongFillHandler, ShortFillHandler  # ✅ Migrated to sagas

# Comprehensive monitoring (NOV 8 - 5 layers)
from bot.monitoring import (
    PriceHealthMonitor,       # ❌ AsyncBot MISSING
    PreOrderDecisionLogger,   # ❌ AsyncBot MISSING
    TPVerificationSystem,     # ❌ AsyncBot MISSING
    AnomalyDetectionSystem,   # ❌ AsyncBot MISSING
    PredictiveDecisionDisplay # ❌ AsyncBot MISSING
)
```

### AsyncBot Imports (bot/strategy/async_gridbot.py)

```python
# Core async components
from bot.api.async_delta_client import AsyncDeltaClient  # ✅ Async REST client
from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager  # ✅ Async WebSocket
from bot.strategy.actors.position_actor import PositionManagerActor  # ✅ Actor pattern
from bot.strategy.actors.order_actor import OrderManagerActor  # ✅ Actor pattern
from bot.strategy.sagas.saga_coordinator import SagaOrchestrator  # ✅ Saga pattern
from bot.strategy.sagas.fill_processing_saga import (
    create_buy_fill_saga,
    create_sell_fill_saga,
)
from bot.strategy.sagas.position_closing_saga import create_emergency_close_all_saga
from bot.strategy.modules.event_store import EventStore  # ✅ Event sourcing
from bot.strategy.modules.grid_calculator import GridCalculator  # ✅ Same module

# MISSING:
# - VolatilityHandler (no volatility checking)
# - 5-layer monitoring system (PriceHealthMonitor, etc.)
# - Reconciliation module (has loop but not full module)
```

**Status**: 🟡 Core dependencies migrated, **monitoring systems missing**

---

## 2. Guardian Bot Integration

### How Old Bot Connects to Guardian

Guardian bot monitors old bot through:

1. **State Files** (Guardian reads these):
   - `bot/reports/positions.json` - Current open positions
   - `bot/reports/state.json` - Pending orders, capacity
   - `bot/reports/bot.pid` - Bot process ID
   - `bot/reports/guardian_health.json` - Health metrics

2. **Shared Configuration**:
   - `GUARDIAN_MAX_ACCOUNT_LOSS_INR` - Max loss threshold
   - `MAX_ACCOUNT_LOSS_INR` - Bot loss limit (must match Guardian)
   - Guardian validates: `MAX_ACCOUNT_LOSS_INR <= GUARDIAN_MAX_ACCOUNT_LOSS_INR`

3. **Guardian Actions on Bot**:
   - Monitors positions for total loss
   - Calls `emergency_kill_all()` if loss exceeds threshold
   - Reads bot PID to check if bot is running
   - Monitors equity floor breaches

### AsyncBot Guardian Integration Status

**What AsyncBot Has**:
- ✅ `bot/reports/positions.json` - **WORKING** (verified Nov 13)
- ✅ `bot/reports/state.json` - **WORKING** (verified Nov 13)
- ✅ `bot/reports/bot.pid` - Created by bot/run.py
- ❌ `bot/reports/guardian_health.json` - **MISSING**

**What's Missing**:
1. **guardian_health.json** - Guardian needs this for health monitoring
2. **Liquidation data export** - Guardian reads margin utilization, liquidation distance
3. **MTM tracking** - Guardian monitors mark-to-market PnL
4. **Real-time equity tracking** - Guardian needs current equity for floor checks

**Guardian Bot Code (Relevant Section)**:

```python
# From bot/guardian/guardian_bot.py:536-610

def monitoring_cycle(self):
    """Execute one monitoring cycle"""
    # Guardian reads liquidation data from bot
    liquidation_data = None
    if self.margin_monitor and self.distance_monitor and self.mtm_tracker:
        liq_status = self.liquidation_monitor.get_status()
        
        # Guardian needs this data structure
        liquidation_data = {
            'margin': {
                'utilization': utilization,
                'zone': margin_zone,
                'total_balance': total_balance,
                'available_balance': available_balance,
                'unrealized_pnl': unrealized_pnl
            },
            'distance': {
                'distance': distance,
                'zone': distance_zone
            },
            'mtm': {
                'current_mtm_inr': current_mtm
            }
        }
    
    # Guardian updates health file for WebUI
    self.health_tracker.update_health(result)
```

**Action Required**: AsyncBot must export liquidation/health data for Guardian

---

## 3. Heartbeat Integration

### Old Bot Heartbeat System

**Internal Heartbeat** (_heartbeat() method - every 15s):
```python
def _heartbeat(self):
    """Periodic heartbeat tasks"""
    # Update heartbeat timestamp for watchdog
    self._last_heartbeat_time = time.time()
    
    # Memory leak prevention
    self._check_memory_usage()
    
    # WebSocket health check
    self._check_websocket_health()
    
    # Periodic volatility safety check
    vol_tracker = get_volatility_tracker()
    self.volatility.check_pending_order_safety(vol_tracker, self.current_price)
    
    # Write monitoring snapshot (for WebUI - every 10s)
    self.monitoring_writer.write_snapshot(self)
    
    # Persist state
    self.position_mgr.persist_runtime_state()
    
    # Check pending orders via REST API for missed fills
    pending_buy = self.position_mgr.get_pending_buy()
    if pending_buy and pending_buy.get('order_id'):
        order_check = self.delta_client.get_order_by_id(order_id)
        if order_state == 'filled':
            # Recover missed fill
            self.fill_detector.process_websocket_fill(fill_data)
    
    # Predictive decision display
    self.predictive_display.display_decision_map(...)
    
    # TP retry queue processing
    # Enforce pending order invariant
```

**External Heartbeat** (continuous_heartbeat.py - separate process):
```python
#!/usr/bin/env python3
def update_heartbeat():
    heartbeat_data = {
        'timestamp': time.time(),
        'status': 'running',
        'pid': os.getpid(),
        'quality': 'good',
        'last_update': datetime.now().isoformat()
    }
    
    with open('.heartbeat', 'w') as f:
        json.dump(heartbeat_data, f)

# Updates .heartbeat file every 5 seconds
```

**PM2 Heartbeat Monitor** (ecosystem.config.js):
```javascript
{
  name: "heartbeat-monitor",
  script: "bot/heartbeat/monitor.py",
  interpreter: "python3",
  autorestart: true
}
```

### AsyncBot Heartbeat System

**What AsyncBot Has**:
```python
async def _heartbeat_loop(self) -> None:
    """Periodic heartbeat tasks."""
    while self._running:
        await asyncio.sleep(15)
        
        # Get state from position actor
        state = await self.position_actor.ask("GET_STATE", {})
        
        # Get metrics
        order_metrics = await self.order_actor.ask("GET_METRICS", {})
        saga_metrics = self.saga_orchestrator.get_metrics()
        
        log.info(f"""
        [HEARTBEAT] Status:
        - Positions: {len(state['open_tranches'])}/{self.position_actor.max_positions}
        - Pending Buy: {'Yes' if state['pending_buy'] else 'No'}
        - Active Orders: {order_metrics['active_orders']}
        - Active Sagas: {saga_metrics['active_sagas']}
        - Fills: {self._fills_processed}
        """)
```

**What's Missing**:
1. ❌ **Memory usage checking** - No `_check_memory_usage()`
2. ❌ **WebSocket health check** - No `_check_websocket_health()`
3. ❌ **Volatility safety check** - No volatility handler integration
4. ❌ **Monitoring snapshot writer** - No `monitoring_writer.write_snapshot()`
5. ❌ **Missed fill recovery** - No REST API polling for pending orders
6. ❌ **Predictive display** - No decision map display
7. ❌ **TP retry queue** - No retry mechanism
8. ❌ **External heartbeat file** - No `.heartbeat` file updates

**Critical Gap**: AsyncBot has NO external heartbeat file integration

---

## 4. PM2 Ecosystem Integration

### Current PM2 Configuration (ecosystem.config.js)

```javascript
module.exports = {
  apps: [
    {
      name: "gridbot-demo",
      script: "bot/run.py",  // ✅ Works with AsyncBot (bot/run.py launches it)
      interpreter: "python3",
      env: {
        TRADING_MODE: "demo",
        HOT_RELOAD: "1"
      },
      autorestart: true,
      max_memory_restart: "500M",
      log_file: "bot/logs/pm2-gridbot-demo.log"
    },
    {
      name: "gridbot-live",
      script: "bot/run.py",  // ✅ Works with AsyncBot
      env: {
        TRADING_MODE: "live"
      }
    },
    {
      name: "guardian-demo",
      script: "bot/guardian/guardian_bot.py",  // ❌ Guardian missing AsyncBot health data
      autorestart: true
    },
    {
      name: "heartbeat-monitor",
      script: "bot/heartbeat/monitor.py",  // ❌ AsyncBot doesn't update heartbeat file
      autorestart: true
    },
    {
      name: "webui-backend",
      script: "webui/backend/app.py",  // ✅ Works with AsyncBot (reads positions.json)
      autorestart: true
    }
  ]
};
```

**Status**:
- ✅ **gridbot-demo/live**: PM2 can launch AsyncBot via bot/run.py
- 🟡 **guardian-demo/live**: PM2 launches Guardian but Guardian can't fully monitor AsyncBot
- ❌ **heartbeat-monitor**: PM2 launches monitor but AsyncBot doesn't feed it
- ✅ **webui-backend**: PM2 launches WebUI which reads AsyncBot files

**Action Required**: Verify PM2 works with AsyncBot, fix Guardian/heartbeat integration

---

## 5. Log Format & Terminal Output Comparison

### Old Bot Log Format (Rich, Detailed)

**Startup Banner**:
```
==================================================================================================
🎯 GRIDBOT v3.0 INITIALIZATION
==================================================================================================
Trading Mode:  🟢 DEMO MODE [TESTNET]
Symbol:       BTCUSD (ID: 27)
Grid Mode:    LONG (Buy low, sell high)
Grid Bounds:  $98,000 - $110,000 (Step: $500)
Reference:    $101,000 (First BUY @ $100,500)
==================================================================================================
✅ All modules initialized successfully
==================================================================================================
```

**Heartbeat Output** (every 15s):
```
💓 [HEARTBEAT] 2025-11-13 10:30:00
   ├─ Positions: 3/5
   ├─ Pending BUY: $100,500
   ├─ Current Price: $101,250
   ├─ Memory: 145.2 MB (↓ 2.3 MB since last)
   ├─ WebSocket: ✅ Healthy (last update: 3s ago)
   ├─ Volatility: ✅ Safe (IV: 35%, RV: 32%)
   └─ Next Action: If price → $100,000, BUY 1 BTC
```

**Order Placement Log**:
```
==================================================================================================
🎯 ORDER DECISION - BUY ENTRY
==================================================================================================
📊 Market Context:
   Current Price:    $100,250
   Grid Level:       $100,000
   Volatility:       ✅ Safe (IV: 35%, RV: 32%)
   
💰 Order Details:
   Side:             BUY
   Price:            $100,000
   Size:             1.0 BTC
   Type:             LIMIT (post-only)
   Client ID:        BOT-ENTRY-BUY-1699888800123
   
✅ Safety Checks Passed:
   ✓ Price not stale (updated 2s ago)
   ✓ Within grid bounds ($98,000 - $110,000)
   ✓ Volatility safe
   ✓ Capacity available (3/5 positions)
   ✓ No duplicate order exists
   
📡 Placing order via Delta Exchange API...
==================================================================================================
✅ BUY ORDER PLACED - Order ID: 1033869680
==================================================================================================
```

### AsyncBot Log Format (Minimal)

**Startup**:
```
2025-11-13 10:30:00 | INFO | Starting AsyncGridBot - Mode: LONG, Symbol: BTCUSD
2025-11-13 10:30:01 | INFO | Heartbeat loop started
2025-11-13 10:30:01 | INFO | Monitoring loop started
2025-11-13 10:30:01 | INFO | Health check loop started
2025-11-13 10:30:01 | INFO | Reconciliation loop started
```

**Heartbeat Output**:
```
2025-11-13 10:30:15 | INFO | 
[HEARTBEAT] Status:
- Positions: 3/5
- Pending Buy: Yes
- Pending Sell: No
- Active Orders: 1
- Active Sagas: 0
- Fills: 5
```

**Order Placement Log**:
```
2025-11-13 10:30:20 | INFO | Placing BUY order at 100000.0
2025-11-13 10:30:21 | INFO | Order placed: 1033869680
```

**Comparison**:
| Feature | Old Bot | AsyncBot | Status |
|---------|---------|----------|--------|
| **Startup banner** | ✅ Rich ASCII art | ❌ Single line | 🟡 Needs enhancement |
| **Emojis** | ✅ Extensive | 🟡 Minimal | 🟡 Needs more |
| **Box drawing** | ✅ ASCII tables | ❌ None | 🟡 Needs enhancement |
| **Pre-order safety checks** | ✅ Detailed log | ❌ Not logged | ❌ Missing |
| **Volatility status** | ✅ Logged every heartbeat | ❌ Not logged | ❌ Missing |
| **Memory usage** | ✅ Logged | ❌ Not logged | ❌ Missing |
| **WebSocket health** | ✅ Logged | ❌ Not logged | ❌ Missing |
| **Predictive actions** | ✅ "Next action if price..." | ❌ None | ❌ Missing |
| **Order context** | ✅ Full market context | ❌ Minimal | 🟡 Needs enhancement |

---

## 6. Monitoring Systems Integration

### Old Bot: 5-Layer Monitoring System (NOV 8)

```python
from bot.monitoring import (
    PriceHealthMonitor,       # Layer 1: Prevent orders with stale price
    PreOrderDecisionLogger,   # Layer 2: Transparency before every order
    TPVerificationSystem,     # Layer 3: Detect orphaned positions
    AnomalyDetectionSystem,   # Layer 4: Alert on dangerous patterns
    PredictiveDecisionDisplay # Layer 5: Show next actions
)
```

**Layer 1: Price Health Monitor**
- Checks price staleness before every order
- Prevents orders with stale WebSocket data
- Triggers REST API fallback if needed

**Layer 2: Pre-Order Decision Logger**
- Logs full context before placing order
- Shows safety check results
- Provides transparency

**Layer 3: TP Verification System**
- Scans for positions without TP orders
- Creates orphaned TP queue
- Retries TP placement

**Layer 4: Anomaly Detection**
- Detects duplicate orders at same price
- Alerts on abnormal patterns
- Prevents strategy violations

**Layer 5: Predictive Decision Display**
- Shows "Next action if price → $X"
- Displays decision map
- Helps user understand bot logic

### AsyncBot Monitoring Status

**What AsyncBot Has**:
- ✅ Basic metrics (positions, orders, sagas)
- ✅ Health check loop (every 30s)
- ✅ Monitoring loop (writes to file every 5s)

**What's Missing**:
- ❌ **All 5 monitoring layers**
- ❌ Price health monitoring
- ❌ Pre-order decision logging
- ❌ TP verification system
- ❌ Anomaly detection
- ❌ Predictive decision display

**Critical Gap**: AsyncBot has NO comprehensive monitoring system

---

## 7. Integration Action Plan

### CRITICAL (Must Implement)

1. **Guardian Health Data Export** (High Priority)
   - [ ] Add liquidation data collection to AsyncBot
   - [ ] Export `guardian_health.json` with margin/distance/MTM
   - [ ] Ensure Guardian can monitor AsyncBot positions
   - **Impact**: Without this, Guardian cannot enforce loss limits

2. **External Heartbeat File** (High Priority)
   - [ ] Add `.heartbeat` file updates to _heartbeat_loop()
   - [ ] Write heartbeat every 5 seconds
   - [ ] Include timestamp, PID, status, quality
   - **Impact**: Without this, external monitors think bot is dead

3. **Missed Fill Recovery** (Critical)
   - [ ] Add REST API polling for pending orders in heartbeat
   - [ ] Detect fills that WebSocket missed
   - [ ] Trigger fill processing saga on recovery
   - **Impact**: Without this, bot can miss fills if WebSocket drops

4. **Volatility Handler Integration** (Critical)
   - [ ] Port VolatilityHandler to async
   - [ ] Add volatility checks to heartbeat
   - [ ] Halt trading if volatility exceeds thresholds
   - **Impact**: Without this, bot trades in unsafe conditions

### IMPORTANT (Should Implement)

5. **Enhanced Logging System** (Medium Priority)
   - [ ] Add rich startup banner (ASCII art, emojis)
   - [ ] Add pre-order decision logging
   - [ ] Add box-drawn tables for status
   - [ ] Add memory/WebSocket health to heartbeat
   - **Impact**: Harder to debug, less user-friendly

6. **5-Layer Monitoring System** (Medium Priority)
   - [ ] Port all 5 monitoring layers to async
   - [ ] Add PriceHealthMonitor
   - [ ] Add PreOrderDecisionLogger
   - [ ] Add TPVerificationSystem
   - [ ] Add AnomalyDetectionSystem
   - [ ] Add PredictiveDecisionDisplay
   - **Impact**: Reduced safety, less transparency

7. **Memory & WebSocket Health Checks** (Medium Priority)
   - [ ] Add `_check_memory_usage()` to heartbeat
   - [ ] Add `_check_websocket_health()` to heartbeat
   - [ ] Log warnings if memory/WS unhealthy
   - **Impact**: Cannot detect memory leaks or WS issues

### NICE TO HAVE (Optional)

8. **TP Retry Queue** (Low Priority)
   - [ ] Add TP retry mechanism to heartbeat
   - [ ] Process retry queue every heartbeat
   - [ ] Track retry attempts
   - **Impact**: Minor - emergency TP already in place

9. **Predictive Decision Display** (Low Priority)
   - [ ] Add decision map to heartbeat output
   - [ ] Show "Next action if price → $X"
   - **Impact**: User experience only

10. **PM2 Configuration Review** (Low Priority)
    - [ ] Test AsyncBot with PM2
    - [ ] Verify auto-restart works
    - [ ] Verify log rotation works
    - **Impact**: PM2 likely works already

---

## 8. Bot/Run.py Integration Check

### Current Bot Launcher (bot/run.py)

```python
# Line 138-149: Guardian validation
# Validate that Guardian and Trader loss limits are consistent
trader_max_loss = float(os.getenv('MAX_ACCOUNT_LOSS_INR', 5000))
guardian_max_loss = float(os.getenv('GUARDIAN_MAX_ACCOUNT_LOSS_INR', 7500))

if trader_max_loss > guardian_max_loss:
    log.error("❌ CONFIGURATION ERROR!")
    log.error(f"   Trader MAX_ACCOUNT_LOSS_INR ({trader_max_loss}) > Guardian MAX ({guardian_max_loss})")
    log.error("See grid_config.env for MAX_ACCOUNT_LOSS_INR and GUARDIAN_MAX_ACCOUNT_LOSS_INR")
    sys.exit(1)
```

**Status**: ✅ **Guardian validation present in bot/run.py**

This validation works for AsyncBot since bot/run.py launches it. However, Guardian cannot fully monitor AsyncBot without health file exports.

---

## 9. Summary Matrix

| Integration Point | Old GridBot | AsyncBot | Status | Priority |
|-------------------|-------------|----------|--------|----------|
| **Guardian Health File** | ✅ Exports guardian_health.json | ❌ Missing | 🔴 Critical | HIGH |
| **External Heartbeat** | ✅ Updates .heartbeat file | ❌ Missing | 🔴 Critical | HIGH |
| **Missed Fill Recovery** | ✅ REST API polling | ❌ Missing | 🔴 Critical | HIGH |
| **Volatility Handler** | ✅ Full integration | ❌ Missing | 🔴 Critical | HIGH |
| **5-Layer Monitoring** | ✅ All 5 layers | ❌ Missing | 🟡 Important | MEDIUM |
| **Rich Logging** | ✅ Emojis, tables, banners | 🟡 Minimal | 🟡 Important | MEDIUM |
| **Memory Health Check** | ✅ Checked every heartbeat | ❌ Missing | 🟡 Important | MEDIUM |
| **WebSocket Health Check** | ✅ Checked every heartbeat | ❌ Missing | 🟡 Important | MEDIUM |
| **TP Retry Queue** | ✅ Implemented | ❌ Missing | 🟢 Optional | LOW |
| **Predictive Display** | ✅ Implemented | ❌ Missing | 🟢 Optional | LOW |
| **PM2 Configuration** | ✅ Configured | ✅ Configured | ✅ Good | LOW |
| **Positions Export** | ✅ Working | ✅ Working | ✅ Good | - |
| **State Export** | ✅ Working | ✅ Working | ✅ Good | - |

---

## 10. Next Steps

### Immediate (Tonight)

1. ✅ Create this integration audit document
2. 🔄 Implement Guardian health file export
3. 🔄 Implement external heartbeat file updates
4. 🔄 Add missed fill recovery to heartbeat loop

### Short Term (This Week)

5. Port VolatilityHandler to async
6. Add memory/WebSocket health checks
7. Enhance logging format (startup banner, emojis, tables)

### Medium Term (Next Week)

8. Port 5-layer monitoring system to async
9. Add TP retry queue to heartbeat
10. Add predictive decision display

### Testing

11. Test AsyncBot with Guardian bot running
12. Test AsyncBot with PM2 (auto-restart, log rotation)
13. Test AsyncBot with external heartbeat monitor
14. Verify all state files update correctly

---

## 11. Risk Assessment

**Without These Integrations**:

1. **Guardian cannot monitor AsyncBot properly** 
   - Risk: Loss limits not enforced
   - Severity: 🔴 CRITICAL
   - Mitigation: Implement guardian_health.json export ASAP

2. **External monitors think bot is dead**
   - Risk: False alarms, unnecessary restarts
   - Severity: 🟡 MEDIUM
   - Mitigation: Implement .heartbeat file updates

3. **Fills may be missed if WebSocket drops**
   - Risk: Positions without entry, strategy breaks
   - Severity: 🔴 CRITICAL
   - Mitigation: Implement REST API polling in heartbeat

4. **Bot trades in high volatility**
   - Risk: Unsafe market conditions, large losses
   - Severity: 🔴 CRITICAL
   - Mitigation: Port VolatilityHandler to async

5. **No monitoring transparency**
   - Risk: Harder to debug issues
   - Severity: 🟡 MEDIUM
   - Mitigation: Enhance logging system

---

*End of Integration Audit*
