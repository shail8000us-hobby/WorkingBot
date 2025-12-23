# Price Update Fix - November 20, 2025

**Issue:** UnifiedAPIClient price cache not being updated from WebSocket  
**Status:** ✅ **FIXED**

---

## 🐛 **The Problem**

The bot was updating its own `self.current_price` and `self._last_price_update` from WebSocket ticker messages, but **NOT** updating the `UnifiedAPIClient`'s price cache.

This could cause:
- UnifiedAPIClient thinks price is stale
- Unnecessary REST API fallback
- "Price stale" warnings

---

## ✅ **The Fix**

**File:** `bot/strategy/async_gridbot.py` line ~1577

**Added:**
```python
# NOV 20: Update UnifiedAPIClient price cache
self.api_client.update_price_from_websocket(price)
```

**Location:** In `_handle_ticker_update()` method, right after updating bot's own price.

---

## 🔄 **Data Flow (Fixed)**

### **Before:**
```
WebSocket Ticker Update
    ↓
_handle_ticker_update()
    ↓
self.current_price = price ✅
self._last_price_update = time.time() ✅
    ↓
UnifiedAPIClient.current_price = ??? ❌ (NOT UPDATED)
    ↓
UnifiedAPIClient thinks price is stale after 10s
```

### **After:**
```
WebSocket Ticker Update
    ↓
_handle_ticker_update()
    ↓
self.current_price = price ✅
self._last_price_update = time.time() ✅
self.api_client.update_price_from_websocket(price) ✅ (NEW)
    ↓
UnifiedAPIClient.current_price = price ✅
UnifiedAPIClient.last_price_update = time.time() ✅
    ↓
No stale price warnings!
```

---

## 📋 **UnifiedAPIClient Price Logic**

### **Price Staleness Check:**
```python
def _is_price_stale(self) -> bool:
    """Check if WebSocket price is stale"""
    if self.last_price_update == 0:
        return True
    
    age = time.time() - self.last_price_update
    return age > self.price_stale_threshold  # 10 seconds
```

### **Automatic Fallback:**
```python
async def get_current_price(self) -> float:
    """Get current price with automatic fallback"""
    # If WebSocket is active and price is fresh, use it
    if self.ws_active and self.current_price and not self._is_price_stale():
        return self.current_price
    
    # Otherwise, fall back to REST
    return await self._get_price_from_rest()
```

---

## ✅ **Result**

- ✅ UnifiedAPIClient price cache stays fresh
- ✅ No unnecessary REST fallback
- ✅ No "price stale" warnings
- ✅ WebSocket price used efficiently

---

**Fixed:** November 20, 2025, 2:30 AM  
**Status:** ✅ **RESOLVED**
