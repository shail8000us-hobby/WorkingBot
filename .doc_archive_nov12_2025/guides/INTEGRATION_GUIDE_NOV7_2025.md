# Integration Guide - Nov 7, 2025 Bug Fixes

## Overview

This guide explains how to integrate the 4 critical bug fixes into your running bot.

**Fixes Implemented:**
- ✅ BUG #1: Race condition (mutex + idempotent)
- ✅ BUG #2: Off-grid orders (boundary validation)
- ✅ BUG #3: Fill detection delay (adaptive REST polling)
- ✅ BUG #4: Circuit breaker cascade (error classification)

---

## Integration Steps

### Step 1: Integrate BUG #3 Fix (Adaptive REST Polling)

The adaptive REST polling requires manual integration into your bot startup code.

**Location**: Your main bot entry point (e.g., `bot/runner.py` or `bot/main.py`)

**Code to Add** (after WebSocket connection):

```python
# After connecting WebSocket manager
ws_manager.connect()

# ✅ START ADAPTIVE REST POLLING (BUG #3 fix)
# This catches fills that WebSocket might miss
try:
    from bot.api.delta_rest_client import DeltaRestClient
    
    # Create or reuse API client
    api_client = DeltaRestClient(
        api_key=config.API_KEY,
        api_secret=config.API_SECRET
    )
    
    # Start adaptive polling (2s high vol, 10s normal)
    ws_manager.start_adaptive_rest_polling(api_client)
    log.info("✅ Adaptive REST polling started")
    
except Exception as e:
    log.error(f"⚠️ Failed to start adaptive REST polling: {e}")
    log.warning("Bot will rely only on WebSocket for fill detection")
```

**Why**: This starts a background thread that polls the REST API every 2-10 seconds (adaptive based on volatility) to catch any fills that the WebSocket might miss.

---

### Step 2: Integrate Fill Handler Callback (BUG #1 fix)

The fill handler needs to clear pending order tracking when orders fill.

**Location**: Your fill event handler (where `ws_manager.on_fill()` callback is registered)

**Code to Modify**:

```python
def handle_fill_event(fill_data: dict):
    """Handle fill event from WebSocket"""
    order_id = fill_data['order_id']
    fill_price = fill_data['fill_price']
    side = fill_data['side']
    
    # ✅ CLEAR PENDING ORDER TRACKING (BUG #1 fix)
    # This prevents duplicate order placement at the same price
    order_manager.clear_pending_order_tracking(fill_price, side)
    
    # Continue with existing fill logic...
    log.info(f"✅ Fill processed: {side} @ ${fill_price:,.0f}")
    
    # Place take-profit order
    if side == 'buy':
        tp_price = fill_price + config.TAKE_PROFIT
        order_manager.place_sell_order(tp_price)
    elif side == 'sell':
        tp_price = fill_price - config.TAKE_PROFIT
        order_manager.place_buy_order(tp_price)

# Register callback
ws_manager.on_fill(handle_fill_event)
```

**Why**: This clears the pending order tracking so the bot can place new orders at that price level if needed.

---

### Step 3: (Optional) Integrate Circuit Breaker (BUG #4 fix)

The circuit breaker can be integrated into your API client wrapper.

**Location**: `bot/api/delta_rest_client.py` or your API wrapper

**Code to Add**:

```python
from bot.api.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

class DeltaRestClient:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # ✅ INITIALIZE CIRCUIT BREAKER (BUG #4 fix)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # Trip after 5 consecutive errors
            timeout=30.0,  # 30s cooldown (15s during high volatility)
            volatility_threshold=0.02  # 2% volatility threshold
        )
    
    def place_order(self, **kwargs):
        """Place order with circuit breaker protection"""
        try:
            # Execute API call through circuit breaker
            return self.circuit_breaker.call(
                self._place_order_internal,
                endpoint='place_order',
                **kwargs
            )
        except CircuitBreakerOpenError as e:
            log.error(f"🚨 Circuit breaker OPEN: {e}")
            return {'success': False, 'error': 'Circuit breaker open'}
    
    def _place_order_internal(self, **kwargs):
        """Internal API call (without circuit breaker)"""
        # Your existing place_order implementation
        response = requests.post(...)
        return response.json()
    
    def cancel_order(self, **kwargs):
        """Cancel order with circuit breaker protection"""
        try:
            return self.circuit_breaker.call(
                self._cancel_order_internal,
                endpoint='cancel_order',
                **kwargs
            )
        except CircuitBreakerOpenError as e:
            log.error(f"🚨 Circuit breaker OPEN: {e}")
            return {'success': False, 'error': 'Circuit breaker open'}
    
    def _cancel_order_internal(self, **kwargs):
        """Internal API call (without circuit breaker)"""
        # Your existing cancel_order implementation
        response = requests.delete(...)
        return response.json()
    
    def update_volatility(self, volatility: float):
        """Update circuit breaker volatility (for adaptive timeout)"""
        self.circuit_breaker.update_volatility(volatility)
```

**Why**: This protects against API cascading failures while excluding expected errors (404/409) from the failure count.

---

## Verification Steps

### 1. Verify BUG #1 Fix (No Duplicate Orders)

**Run this command** to check for duplicate orders at the same price:

```powershell
# Check logs for duplicate order placement
Get-Content logs\pm2-gridbot-demo-combined.log | Select-String -Pattern "BUY order placed|SELL order placed" | Group-Object -Property {$_ -replace '.*@ \$([0-9,]+).*','$1'} | Where-Object {$_.Count -gt 1}
```

**Expected**: No groups with Count > 1 (no duplicates at same price)

---

### 2. Verify BUG #2 Fix (All Orders Grid-Aligned)

**Run this Python script**:

```python
import re

# Parse logs
with open('logs/pm2-gridbot-demo-combined.log', 'r') as f:
    logs = f.read()

# Extract all order prices
prices = re.findall(r'@ \$([0-9,]+)', logs)
prices = [int(p.replace(',', '')) for p in prices]

# Check grid alignment (step=300, lower=90000)
lower = 90000
step = 300

off_grid = []
for price in prices:
    if (price - lower) % step != 0:
        off_grid.append(price)

if off_grid:
    print(f"❌ OFF-GRID ORDERS FOUND: {off_grid}")
else:
    print("✅ All orders grid-aligned")
```

**Expected**: "✅ All orders grid-aligned"

---

### 3. Verify BUG #3 Fix (Fast Fill Detection)

**Check fill detection latency**:

```powershell
# Extract fill detection events with timestamps
Get-Content logs\pm2-gridbot-demo-combined.log | Select-String -Pattern "FILL DETECTED" | Select-Object -Last 20
```

**Look for**:
- `detection_method`: Should show "websocket_orders" (primary) or "rest_polling" (backup)
- Latency: Should be < 5 seconds between order placement and fill detection

---

### 4. Verify BUG #4 Fix (Circuit Breaker Works)

**Check circuit breaker behavior**:

```powershell
# Check for 404 errors that shouldn't trigger circuit breaker
Get-Content logs\pm2-gridbot-demo-combined.log | Select-String -Pattern "404|not found|Circuit breaker" | Select-Object -Last 20
```

**Expected**:
- 404 errors logged as "Expected error (404) - not counted"
- Circuit breaker should NOT trip on 404 errors
- Circuit breaker should only trip on 5+ consecutive 500/502/503 errors

---

## Testing Checklist

Before production deployment, verify:

- [ ] **No duplicate orders** at the same price (run for 1 hour)
- [ ] **All orders grid-aligned** (check every order placement)
- [ ] **Fill detection < 5s** (average across 10+ fills)
- [ ] **Circuit breaker stable** (doesn't trip on 404 errors)
- [ ] **Adaptive REST polling running** (check logs for "Adaptive REST polling started")
- [ ] **Pending order tracking cleared** on fills (check memory doesn't grow)

---

## Rollback Plan

If issues occur, you can disable individual fixes:

### Disable Adaptive REST Polling (BUG #3)

```python
# In your bot startup code
ws_manager.stop_adaptive_rest_polling()
```

### Disable Circuit Breaker (BUG #4)

```python
# In your API client
# Comment out circuit_breaker.call() and call internal methods directly
return self._place_order_internal(**kwargs)
```

### Revert to Previous Code

```powershell
# Restore from backup
git checkout HEAD~1 bot/strategy/modules/order_manager.py
git checkout HEAD~1 bot/strategy/modules/grid_calculator.py
git checkout HEAD~1 bot/delta_websocket/ws_manager.py
```

---

## Monitoring Dashboard

**Key Metrics to Monitor:**

1. **Order Placement Rate**: Should be steady, no bursts of duplicates
2. **Fill Detection Latency**: < 5s average
3. **Grid Integrity**: 100% of orders grid-aligned
4. **Circuit Breaker State**: Should stay CLOSED during normal trading
5. **Pending Orders Count**: Should decrease when orders fill

**Log Messages to Watch For:**

- ✅ `"Adaptive REST polling started"` - Confirms BUG #3 fix active
- ✅ `"FILL DETECTED (via orders channel - PRIMARY)"` - Normal fill detection
- ⚠️ `"FILL MISSED BY WEBSOCKET! Detected via REST"` - Backup working
- ⚠️ `"BUY order already pending @ $X"` - Duplicate prevented (good)
- 🚨 `"Circuit breaker OPEN"` - Only on 5+ consecutive API errors (investigate)
- 🚨 `"OFF-GRID"` - Should never happen with BUG #2 fix

---

## Support

If you encounter issues:

1. **Check logs** for error messages
2. **Run verification scripts** above
3. **Check `BUG_FIX_IMPLEMENTATION_STATUS_NOV7_2025.md`** for implementation details
4. **Review `STRESS_TEST_FRAMEWORK.md`** for comprehensive testing

---

**Document Version**: 1.0  
**Last Updated**: Nov 7, 2025  
**Status**: Ready for integration
