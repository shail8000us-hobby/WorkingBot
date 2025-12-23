# Price Stale Issue Fix - November 20, 2025

**Issue:** Price stale warnings appearing in logs  
**Status:** 🔧 **INVESTIGATING**

---

## 🐛 **THE PROBLEM**

**Symptoms from logs:**
```
⚠️ PRICE STALE: $89,693.50 | Age: 28.2s | Source: REST_API
⚠️ PRICE STALE: $89,693.50 | Age: 33.2s | Source: REST_API
🚨 [REST FALLBACK] WebSocket starved for 28.2s > 35s threshold
⚠️ UNSAFE TO PLACE ORDERS - Price data too old!
```

**What's Happening:**
- WebSocket ticker updates are not keeping UnifiedAPIClient's price cache fresh
- Price age exceeds 10s threshold
- System falls back to REST API
- Orders blocked due to stale price

---

## 🔍 **ROOT CAUSE ANALYSIS**

### **Potential Issues:**

**1. WebSocket Not Receiving Ticker Updates**
- Channel subscription might be incorrect
- Handler registration might be wrong
- WebSocket connection might be unstable

**2. Price Update Not Being Called**
- `update_price_from_websocket()` might not be called
- Ticker handler might not be triggered
- Message routing might be broken

**3. Timing Issue**
- Price updates happening but too infrequent
- 10s threshold might be too aggressive
- WebSocket heartbeat might be slow

---

## ✅ **FIXES APPLIED**

### **1. Added Debug Logging**

**File:** `bot/api/unified_api_client.py`

**Change 1: Log price updates**
```python
def update_price_from_websocket(self, price: float):
    """Update price from WebSocket"""
    self.current_price = price
    self.last_price_update = time.time()
    log.debug(f"💚 UnifiedAPIClient price updated: ${price:,.2f} (age will be 0s)")
```

**Change 2: Log staleness checks**
```python
def _is_price_stale(self) -> bool:
    """Check if WebSocket price is stale"""
    if self.last_price_update == 0:
        log.warning("⚠️ PRICE STALE: No price update received yet")
        return True
    
    age = time.time() - self.last_price_update
    is_stale = age > self.price_stale_threshold
    
    if is_stale:
        log.warning(f"⚠️ PRICE STALE: ${self.current_price:,.2f} | Age: {age:.1f}s")
    
    return is_stale
```

**Purpose:**
- Identify if `update_price_from_websocket()` is being called
- See exact age when price is considered stale
- Determine if issue is with updates or threshold

---

## 🧪 **TESTING STEPS**

### **1. Check if Price Updates Are Received**
```bash
# Start bot and watch logs
python3 -m bot.strategy.async_gridbot 2>&1 | grep "UnifiedAPIClient price updated"

# Expected: Should see frequent updates (every few seconds)
# If NOT seen: WebSocket ticker updates are not being received
```

### **2. Check Staleness Warnings**
```bash
# Watch for stale price warnings
python3 -m bot.strategy.async_gridbot 2>&1 | grep "PRICE STALE"

# Expected: Should NOT see these if updates are working
# If seen: Check the age value
```

### **3. Check WebSocket Subscription**
```bash
# Check if ticker channel is subscribed
python3 -m bot.strategy.async_gridbot 2>&1 | grep "Subscribed to WebSocket"

# Expected: "✅ Subscribed to WebSocket channels"
```

---

## 🔧 **POTENTIAL SOLUTIONS**

### **Solution 1: Increase Stale Threshold**
If updates are happening but infrequent:

```python
# bot/api/unified_api_client.py
self.price_stale_threshold = 30  # Increase from 10 to 30 seconds
```

**When to use:** If ticker updates come every 15-20 seconds

---

### **Solution 2: Fix WebSocket Subscription**
If ticker updates are not being received:

```python
# Check channel name mismatch
# Bot registers: "v2/ticker"
# Subscription uses: subscribe_ticker(symbol)

# Might need to verify channel name in AsyncWebSocketManager
```

**When to use:** If no "💚 UnifiedAPIClient price updated" logs

---

### **Solution 3: Add Periodic REST Polling**
If WebSocket is unreliable:

```python
# Add periodic REST price fetch as backup
async def _periodic_price_update(self):
    while self._running:
        if self._is_price_stale():
            price = await self.api_client.get_current_price()
            # This will trigger REST fallback automatically
        await asyncio.sleep(5)
```

**When to use:** If WebSocket frequently goes stale

---

## 📊 **DIAGNOSTIC CHECKLIST**

Run bot and check:

- [ ] "✅ Subscribed to WebSocket channels" appears in logs
- [ ] "💚 UnifiedAPIClient price updated" appears frequently
- [ ] "⚠️ PRICE STALE" does NOT appear
- [ ] "🚨 [REST FALLBACK]" does NOT appear
- [ ] Orders are placed successfully

**If all checked:** Issue is resolved  
**If any unchecked:** Follow corresponding solution

---

## 🎯 **NEXT STEPS**

1. **Run bot with new logging**
2. **Monitor for 5 minutes**
3. **Check which logs appear**
4. **Apply appropriate solution**

---

## 📝 **EXPECTED BEHAVIOR**

**Healthy System:**
```
💚 UnifiedAPIClient price updated: $89,693.50 (age will be 0s)
💚 UnifiedAPIClient price updated: $89,694.00 (age will be 0s)
💚 UnifiedAPIClient price updated: $89,693.75 (age will be 0s)
... (every few seconds)
```

**Unhealthy System:**
```
⚠️ PRICE STALE: $89,693.50 | Age: 28.2s
🚨 [REST FALLBACK] WebSocket starved
⚠️ UNSAFE TO PLACE ORDERS
```

---

**Status:** 🔧 **AWAITING TEST RESULTS**  
**Next Action:** Run bot and check logs  
**Created:** November 20, 2025, 3:15 AM
