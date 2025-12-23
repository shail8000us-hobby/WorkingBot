# Async Bot No Orders - Root Cause Analysis

**Date**: November 12, 2025  
**Status**: CRITICAL BUG FOUND  
**Severity**: HIGH - Bot cannot trade

---

## Problem Statement

After shifting from threaded to async production system, the bot:
- ✅ Connects successfully
- ✅ Receives WebSocket data (ticker, heartbeats)
- ✅ All actors and sagas running properly
- ❌ **NOT placing ANY orders**

---

## Root Cause Identified

### Missing: Initial Order Placement Logic

The async bot (`bot/strategy/async_gridbot.py`) is **missing the entire order entry logic**:

1. **No Initial Order Placement**
   - Threaded bot: Places initial order on startup (lines 1900-2100 in `gridbot.py`)
   - Async bot: No startup order placement code exists

2. **No Ticker-Based Entry Logic**
   - Threaded bot: Has `_handle_price_update()` that checks if orders should be placed (line 1320+)
   - Async bot: `_handle_ticker_update()` only has `pass` (line 352-355)

3. **Only Reactive to Fills**
   - Async bot only processes fills via `_handle_user_trades()` and `_process_fill()`
   - But without initial orders, there are no fills to process!

---

## Evidence from Logs

```
2025-11-12 18:23:51.643 | INFO | bot.strategy.async_gridbot:_heartbeat_loop:374 - 
                [HEARTBEAT] Status:
                - Positions: 0/5
                - Pending Buy: No
                - Pending Sell: No
                - Active Orders: 0
                - Active Sagas: 0
                - Fills: 0
```

Bot runs perfectly but **never places the first order**.

---

## What the Threaded Bot Does (That Async Bot Doesn't)

### 1. Startup Order Placement (gridbot.py:1900-2100)
```python
# At startup, checks:
- Volatility safety
- No existing pending orders
- Calculates initial grid level
- Places MAKER BUY order with post_only=True
```

### 2. Proactive Order Management (gridbot.py:1320-1400)
```python
def _handle_price_update(self, ticker_data):
    # On every price update:
    - Update current_price
    - Check volatility
    - Place orders if:
      - No pending orders exist
      - Capacity available
      - Volatility safe
      - Price within grid bounds
```

### 3. Volatility-Aware Recovery
- Monitors volatility on every tick
- Places orders when volatility becomes safe
- Cancels orders if volatility becomes unsafe

---

## Missing Components in Async Bot

| Component | Threaded Bot | Async Bot | Status |
|-----------|--------------|-----------|--------|
| Initial order placement | ✅ Yes | ❌ No | **MISSING** |
| Ticker-based entry logic | ✅ Yes | ❌ No | **MISSING** |
| Proactive order management | ✅ Yes | ❌ No | **MISSING** |
| Volatility integration | ✅ Yes | ❌ No | **MISSING** |
| Fill processing | ✅ Yes | ✅ Yes | Working |
| WebSocket handling | ✅ Yes | ✅ Yes | Working |
| Actor/Saga pattern | ❌ No | ✅ Yes | Working |

---

## Required Fixes

### Priority 1: Add Initial Order Placement
**File**: `bot/strategy/async_gridbot.py`
**Method**: `start()` (after WebSocket connects)

```python
async def start(self):
    # ... existing code ...
    
    # After WebSocket connection
    await self._subscribe_channels()
    
    # 🔥 ADD THIS: Place initial order
    await self._place_initial_order()
    
    # Start async tasks
    async_tasks = [...]
```

### Priority 2: Implement Ticker-Based Entry Logic
**File**: `bot/strategy/async_gridbot.py`
**Method**: `_handle_ticker_update()`

```python
async def _handle_ticker_update(self, message: Dict[str, Any]) -> None:
    """Handle ticker updates and check for entry opportunities."""
    try:
        # Extract price
        ticker_data = message.get('mark_price') or message.get('last')
        if not ticker_data:
            return
            
        self.current_price = float(ticker_data)
        
        # Check if should place order
        await self._check_and_place_entry_order()
        
    except Exception as e:
        log.error(f"Ticker update error: {e}")
```

### Priority 3: Add Entry Logic
**File**: `bot/strategy/async_gridbot.py`
**New Method**: `_check_and_place_entry_order()`

```python
async def _check_and_place_entry_order(self) -> None:
    """Check if entry order should be placed."""
    try:
        # Get current state
        state = await self.position_actor.ask("GET_STATE", {})
        
        # Check if pending order exists
        if self.mode == "LONG":
            if state.get("pending_buy"):
                return  # Already have pending order
        else:
            if state.get("pending_sell"):
                return
        
        # Check capacity
        if len(state["open_tranches"]) >= self.position_actor.max_positions:
            return  # At max capacity
        
        # Calculate next entry level
        positions = state["open_tranches"]
        
        if self.mode == "LONG":
            target = self.grid_calc.compute_next_buy_level(positions)
            if target and self.grid_calc.is_within_bounds(target):
                # Use saga to place order
                await self._place_buy_order_saga(target)
        else:
            target = self.grid_calc.compute_next_sell_level(positions)
            if target and self.grid_calc.is_within_bounds(target):
                await self._place_sell_order_saga(target)
                
    except Exception as e:
        log.error(f"Entry check error: {e}")
```

---

## Testing Plan

1. ✅ Stop async bot (completed)
2. ❌ Implement missing order logic
3. ❌ Test in shadow mode (parallel run)
4. ❌ Verify initial order placement
5. ❌ Verify subsequent orders after fills
6. ❌ Test volatility integration
7. ❌ Production cutover

---

## Impact Assessment

**Current State**: Bot is in **read-only mode** - cannot trade at all

**Business Impact**:
- No trading activity = No profit potential
- Shadow mode test was misleading (it only tested fill processing, not order entry)
- Critical issue that went undetected because shadow mode had existing positions

**Why Missed in Testing**:
- Shadow mode validation focused on fill processing (which works)
- Assumed existing orders would trigger fills for testing
- Never tested "cold start" scenario with zero positions

---

## Immediate Action Required

1. **STOP** async bot (✅ completed)
2. **REVERT** to threaded bot temporarily
3. **FIX** async bot order logic
4. **TEST** cold start scenario
5. **RE-VALIDATE** in shadow mode
6. **CUTOVER** when confirmed working

---

## Lessons Learned

1. **Test cold start scenarios**: Always test with zero positions
2. **Complete feature parity**: Ensure ALL logic is ported, not just happy paths
3. **Integration testing**: Shadow mode needs to cover full lifecycle
4. **Monitoring**: Need alerts when bot has zero orders for extended period

---

## Status: AWAITING FIX

**Next Steps**: Implement missing order entry logic in async bot
