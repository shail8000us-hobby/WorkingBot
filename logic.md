# GridBot Trading Logic & Architecture

**Last Updated:** November 20, 2025  
**Bot Version:** AsyncGridBot v2.0 + State Machine Coordinator  
**Architecture:** Single Process, Clean Slate on Restart, Exchange as Source of Truth

---

## 🎯 Core Philosophy

### Clean Slate Approach (Current Phase)
- **Bot clears memory on every restart**
- **Exchange is the single source of truth**
- **Reconciliation validates everything**
- **No state file loading** (development phase)
- **Event store persists for audit only**

### Why Clean Slate?
1. ✅ Perfect reconciliation every startup
2. ✅ No state corruption issues
3. ✅ Easier debugging and iteration
4. ✅ Predictable behavior
5. ✅ Safe for development phase

### Future: State Persistence
- Once grid logic is bulletproof
- Add state loading as optimization
- Keep reconciliation as safety net

---

## 📁 File Structure

```
bot/strategy/
├── async_gridbot.py              # Main bot (3,530 lines)
│   ├── Lines 961-966:  State coordinator init
│   ├── Lines 1862:     compute_next_buy_level(current_price) ✨ FIX
│   ├── Lines 1918:     compute_next_sell_level(current_price) ✨ FIX
│   ├── Lines 3594-3641: _check_missed_grids()
│   ├── Lines 3643-3680: _execute_recovery()
│   └── Lines 1692-1960: _place_initial_order()
│
├── simple_state_coordinator.py   # State machine (170 lines) ✨ NEW
│   ├── run_startup_sequence()
│   ├── monitor_guardian()
│   └── run_reconciliation_loop()
│
├── actors/
│   ├── position_actor.py         # Position state management
│   └── order_actor.py            # Order placement logic
│
├── sagas/
│   ├── fill_processing_saga.py   # Buy/Sell fill handling
│   └── saga_coordinator.py       # Saga orchestration
│
├── modules/
│   ├── grid_calculator.py        # Grid math
│   │   ├── compute_next_buy_level(positions, current_price)  ✨ CRITICAL
│   │   └── compute_next_sell_level(positions, current_price) ✨ CRITICAL
│   ├── event_store.py            # SQL audit log
│   └── mode_state_manager.py     # LONG/SHORT mode logic
│
└── recovery/                      # NOT USED (standalone exists but not integrated)
    └── (recovery engines exist but bot uses simple inline recovery)

bot/api/
└── unified_api_client.py         # WebSocket + REST with fallback

bot/guardian/
└── guardian_bot.py               # Safety monitor (separate process)

data/
├── bot_events_LONG.db            # Event store (audit only, not loaded)
├── system_state.json             # State coordinator state
└── runtime_state_LONG.json       # NOT LOADED (clean slate approach)
```

---

## 🔄 System Flow

### Startup Sequence

```
1. Bot Starts
   ↓
2. State Coordinator Initializes
   ↓
3. Wait for Guardian GO
   ├─ If RED → Poll every 5s until GREEN
   └─ If GREEN → Continue
   ↓
4. Check for Missed Grids
   ├─ Compare current_price vs reference
   ├─ Calculate missed grid levels
   └─ Log findings
   ↓
5. Attempt Recovery (if missed grids found)
   ├─ Try to place market orders (currently fails - API limitation)
   └─ Continue regardless
   ↓
6. Transition to Normal Trading
   ├─ State coordinator sets: normal_trading
   └─ Bot continues with startup
   ↓
7. Sync from Exchange (CRITICAL)
   ├─ Fetch all open positions
   ├─ Fetch all open orders
   └─ Load into bot memory
   ↓
8. Place Initial Pending Order
   ├─ Calculate: compute_next_buy_level([], current_price)  ✨ KEY FIX
   ├─ Places order BELOW current price (LONG)
   └─ Or ABOVE current price (SHORT)
   ↓
9. Start Background Tasks
   ├─ Guardian monitor (every 1s)
   ├─ Reconciliation (every 5 min)
   ├─ Heartbeat, WebSocket, etc.
   └─ Normal grid trading
```

### Runtime Flow

```
Normal Trading:
├─ Monitor Guardian (every tick)
│  ├─ If HALT → Transition to HALTED state
│  └─ If GO → Continue
│
├─ Process WebSocket Events
│  ├─ Price updates
│  ├─ Order fills
│  └─ Position changes
│
├─ Grid Trading Logic
│  ├─ BUY fills → Place TP + Next BUY
│  └─ SELL fills (TP) → Place Next BUY
│
└─ Reconciliation (every 5 min)
   ├─ Skip if recovery in progress
   ├─ Compare bot state vs exchange
   └─ Log discrepancies

Guardian HALT:
├─ Async bot detects HALT
├─ Transition to HALTED state
├─ Stop placing new orders
└─ Wait for Guardian GO

Guardian GO (after HALT):
├─ Check for missed grids
├─ Attempt recovery
└─ Resume normal trading
```

---

## 🔑 Critical Code Locations

### 1. Initial Order Placement (THE FIX)

**File:** `bot/strategy/async_gridbot.py`  
**Lines:** 1862, 1918

**BEFORE (BROKEN):**
```python
target = self.grid_calc.compute_next_buy_level(positions)
# ❌ Doesn't pass current_price
# ❌ Returns reference price or grid above current price
# ❌ Order gets cancelled: "immediate_execution_post_only"
```

**AFTER (FIXED):**
```python
target = self.grid_calc.compute_next_buy_level(positions, current_price=self.current_price)
# ✅ Passes current_price
# ✅ Returns grid level BELOW current price (LONG)
# ✅ Order stays pending until price drops
```

### 2. Grid Calculator Logic

**File:** `bot/strategy/modules/grid_calculator.py`  
**Lines:** 114-123

```python
def compute_next_buy_level(self, open_positions, current_price=None):
    if open_positions:
        lowest_entry = min(p['entry_price'] for p in open_positions)
    else:
        # ✨ KEY LOGIC
        if current_price and current_price < self.ref:
            # Market is below REF, find nearest grid level below market
            lowest_entry = self.find_nearest_grid_below(current_price)
        else:
            lowest_entry = self.ref
    
    target = lowest_entry - self.step
    return self.quantize_price(target)
```

**Example:**
- Reference: $92,500
- Current: $91,800
- Step: $500
- Result: $91,500 (nearest grid BELOW current price) ✅

### 3. State Coordinator

**File:** `bot/strategy/simple_state_coordinator.py`  
**Lines:** 62-73

```python
async def run_startup_sequence(self):
    log.info("🚀 SYSTEM COORDINATOR - Startup Sequence")
    
    await self._wait_for_guardian()        # Wait for GO signal
    await self._check_and_run_recovery()   # Check missed grids
    
    self._transition_to(SystemState.NORMAL_TRADING, "startup_complete")
    log.info("✅ Startup sequence complete")
```

### 4. Recovery Check

**File:** `bot/strategy/async_gridbot.py`  
**Lines:** 3594-3641

```python
async def _check_missed_grids(self) -> List[float]:
    current_price = self.current_price
    ref = self.grid_calc.ref
    step = self.grid_calc.step
    
    if self.mode == "LONG":
        if current_price < ref:
            num_steps_below = int((ref - current_price) / step)
            if num_steps_below > 0:
                num_missed = min(num_steps_below, 3)  # Max 3
                for i in range(1, num_missed + 1):
                    grid_price = ref - (i * step)
                    if grid_price > current_price:
                        missed_grids.append(grid_price)
    
    return missed_grids
```

---

## 🎭 State Machine States

```
WAITING_FOR_GUARDIAN
  ↓ (Guardian GO)
RECOVERY_CHECK
  ↓
  ├─ No missed grids → NORMAL_TRADING
  └─ Missed grids → RECOVERY_IN_PROGRESS → NORMAL_TRADING
                                              ↓
                                     (Guardian HALT)
                                              ↓
                                           HALTED
                                              ↓
                                     (Guardian GO)
                                              ↓
                                       RECOVERY_CHECK
```

**State File:** `data/system_state.json`
```json
{
  "current_state": "normal_trading",
  "last_transition": "2025-11-20T09:46:33.845272",
  "transition_reason": "startup_complete",
  "guardian_status": "GO",
  "mode": "LONG",
  "recovery_in_progress": false
}
```

---

## 📊 Data Flow

### Clean Slate Approach

```
Startup:
  ├─ ❌ DON'T load runtime_state_LONG.json
  ├─ ❌ DON'T load recovery_state.json
  ├─ ✅ DO fetch positions from exchange
  ├─ ✅ DO fetch orders from exchange
  └─ ✅ DO sync to bot memory

Runtime:
  ├─ ✅ Update bot memory (actors)
  ├─ ✅ Write events to SQL (audit only)
  ├─ ❌ DON'T write runtime_state.json
  └─ ✅ Reconciliation validates every 5 min

Shutdown:
  ├─ ✅ Cancel pending orders (optional)
  ├─ ✅ Close connections
  └─ ❌ DON'T save state (clean slate on restart)
```

### Future: State Persistence

```
Startup:
  ├─ ✅ Load runtime_state_LONG.json (optimization)
  ├─ ✅ Validate against exchange
  ├─ ✅ Reconciliation fixes discrepancies
  └─ ✅ Continue with validated state

Runtime:
  ├─ ✅ Update bot memory
  ├─ ✅ Write runtime_state.json (every change)
  └─ ✅ Reconciliation validates

Shutdown:
  ├─ ✅ Save final state
  └─ ✅ Clean shutdown
```

---

## 🔍 Debugging Guide

### Check Bot Status

```bash
# View logs
pm2 logs gridbot-live --lines 100

# Check state
cat data/system_state.json

# Check if bot has pending orders
pm2 logs gridbot-live --lines 50 | grep -i "pending"

# Check current price
pm2 logs gridbot-live --lines 50 | grep -i "price"
```

### Common Issues

**Issue 1: Order cancelled "immediate_execution_post_only"**
- **Cause:** Bot placing order above current price (LONG) or below (SHORT)
- **Fix:** Ensure `current_price` passed to `compute_next_buy_level()`
- **Location:** Lines 1862, 1918 in `async_gridbot.py`

**Issue 2: No pending order after startup**
- **Cause:** Guardian HALT or price outside grid bounds
- **Check:** `pm2 logs gridbot-live | grep Guardian`
- **Fix:** Wait for Guardian GO signal

**Issue 3: Recovery fails with 400 error**
- **Cause:** Delta Exchange API doesn't support market orders
- **Impact:** None - bot continues with normal trading
- **Future:** Implement limit order recovery

**Issue 4: Bot not syncing from exchange**
- **Cause:** State file loading enabled
- **Fix:** Ensure clean slate approach (don't load runtime_state.json)
- **Location:** Check `_load_recovery_state()` method

---

## 🚀 Quick Start for Developers

### 1. Understand the Flow
```
Read this file → Check AI_CONTEXT.md → Read code in order:
  1. simple_state_coordinator.py (startup flow)
  2. async_gridbot.py (main bot)
  3. grid_calculator.py (grid math)
  4. position_actor.py (state management)
```

### 2. Make Changes
```
1. Stop bot: pm2 stop gridbot-live
2. Edit code
3. Test locally
4. Start bot: pm2 start gridbot-live
5. Watch logs: pm2 logs gridbot-live
```

### 3. Clean Slate Testing
```bash
# Stop bot
pm2 stop gridbot-live

# Clean state
rm -f data/system_state.json data/runtime_state_LONG.json

# Start fresh
pm2 start gridbot-live

# Verify
pm2 logs gridbot-live --lines 100 | grep -E "StateCoordinator|Placing initial"
```

---

## 📝 Key Takeaways

1. **Clean Slate = Predictable Behavior**
   - No state corruption
   - Easy debugging
   - Perfect for development

2. **Exchange is Source of Truth**
   - Always sync from exchange on startup
   - Reconciliation validates everything
   - Bot memory is temporary

3. **State Machine Coordinates Everything**
   - Guardian check → Recovery → Normal trading
   - Clear state transitions
   - No race conditions

4. **Critical Fix: Pass current_price**
   - `compute_next_buy_level(positions, current_price=self.current_price)`
   - Places orders at correct grid level
   - No more "immediate_execution_post_only" errors

5. **Future: Add State Persistence**
   - Once grid logic is perfect
   - Optimization, not requirement
   - Reconciliation remains safety net

---

## 🔗 Related Documentation

- **AI_CONTEXT.md** - Complete project overview
- **STATE_MACHINE_IMPLEMENTATION_COMPLETE.md** - State machine details
- **ASYNC_GRIDBOT_EXECUTIVE_SUMMARY.md** - Bot architecture
- **CONFIG_QUICK_REF.md** - Configuration reference
