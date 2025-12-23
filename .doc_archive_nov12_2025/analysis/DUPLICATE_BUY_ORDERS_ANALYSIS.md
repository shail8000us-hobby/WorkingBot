# 🚨 DUPLICATE BUY ORDERS ANALYSIS

**Date**: October 31, 2025  
**Issue**: Bot placed two identical BUY orders at $109,000  
**Orders**: #1015075838 (10:14 AM) and #1015081634 (10:22 AM)

---

## 📊 LAST 4 ORDERS PLACED

```
1. SELL @ $108,287.50 | Order 1014483986 | open | Oct 30, 20:39:19
   └─ TP order (reduce_only) protecting position

2. BUY  @ $106,287.50 | Order 1014484029 | open | Oct 30, 20:39:22
   └─ Normal grid BUY (this one failed to cancel during volatility halt)

3. BUY  @ $109,000.00 | Order 1015075838 | open | Oct 31, 10:14:06
   └─ Grid BUY placed

4. BUY  @ $109,000.00 | Order 1015081634 | open | Oct 31, 10:22:05
   └─ DUPLICATE BUY at same price! (8 minutes later)
```

---

## 🔍 ROOT CAUSE: SINGLE PENDING BUY ENFORCEMENT FAILURE

### **The Architecture**

The bot is DESIGNED to have **only ONE pending BUY order at a time**:

```python
# bot/strategy/gbot_ws.py design:
# State: pending_buy = Dict or None
# 
# RULE: Only ONE pending buy allowed
# ENFORCEMENT: Cancel old pending buy before placing new one
```

### **What Went Wrong**

**Scenario Reconstruction**:

```
10:14:06 - Place BUY @ $109,000 (Order 1015075838)
           ├─ pending_buy = {order_id: 1015075838, price: 109000}
           └─ Status: Pending on exchange

10:14:XX - Something triggered a new BUY at SAME price ($109,000)
           ├─ Code checks: pending_buy exists at same price
           ├─ Should skip: "Already have pending at this price"
           └─ BUT: Logic failed or concurrent thread bypassed check

10:22:05 - New BUY @ $109,000 (Order 1015081634) placed
           ├─ pending_buy updated = {order_id: 1015081634, price: 109000}
           └─ OLD order 1015075838 orphaned (not tracked, not cancelled)
```

---

## 💥 POSSIBLE CAUSES

### **Cause #1: Price Comparison Precision Issue**

```python
# bot/strategy/gbot_ws.py:1178-1185
def _ensure_single_correct_pending_buy(self):
    current = self.pending_buy.get('price') if self.pending_buy else None
    target = self._compute_target_buy()
    
    # ❌ Floating point comparison - might fail!
    if (self.pending_buy is None) or (abs(float(current) - float(target)) > 1e-9):
        self._cancel_pending_buy()
        self._place_buy_order(target)
```

**If**: `target = 109000.00000001` vs `current = 109000.0`  
**Then**: `abs(109000.00000001 - 109000.0) = 1e-10 < 1e-9`  
**Result**: Thinks price match, but later logic places new order anyway

### **Cause #2: Race Condition in Grid Continuation**

```python
# bot/strategy/gbot_ws.py:704-710 (after TP fill)
if tranche_to_remove and should_place_next:
    if self._try_reserve_order_capacity():
        log.info(f"Grid continuation: placing BUY @ {next_px}")
        order_result = self._place_buy_order(next_px)  # ⬅️ Might not check pending_buy!
```

**If**:
- TP filled at $110,000
- Next BUY should be at $109,000
- But pending_buy already exists at $109,000
- Code might not check and places duplicate

### **Cause #3: Concurrent Thread Bypass**

**Thread A** (Price tick):
```python
with self._state_lock:
    if self._pending_transition:
        return None  # Blocked
    if self.pending_buy:
        self._pending_transition = True  # Lock
# Lock released
self._cancel_pending_buy()
self._place_buy_order(price)
```

**Thread B** (TP fill continuation):
```python
# Runs concurrently during Thread A's cancel/place window
order_result = self._place_buy_order(next_px)  # ⬅️ No transition check!
```

---

## 🎯 VERIFICATION NEEDED

### **Check Order Status on Exchange**

```bash
# Are both orders still active?
# If so, this is CRITICAL - double position exposure
```

**If both filled**:
- 2x position size at same price = Over-leveraged
- Violates max_open logic
- Double capital at risk

**If one filled, one pending**:
- One position untracked (orphaned)
- Pending order might fill later
- Reconciliation mismatch

---

## 🔧 FIX REQUIRED

### **Add Duplicate Price Check in _place_buy_order**

```python
def _place_buy_order(self, price: float) -> Optional[str]:
    """Place BUY order with duplicate price check"""
    price = _quantize(price)
    
    # ✅ CRITICAL: Check if we already have pending buy at this exact price
    with self._state_lock:
        if self.pending_buy:
            pending_price = self.pending_buy.get('price')
            if abs(price - pending_price) < 0.01:  # Within 1 cent
                log.info(f"⏭️  Skipping BUY @ {_fmt_px(price)} - already have pending at {_fmt_px(pending_price)}")
                return self.pending_buy.get('order_id')  # Return existing order ID
    
    # ... rest of placement logic ...
```

### **Add Order Reconciliation in Main Loop**

```python
def _reconcile_pending_orders_periodically(self):
    """
    Check for orphaned orders every 60 seconds
    Query exchange for all open orders and compare with local state
    """
    if time.time() - getattr(self, '_last_recon_time', 0) < 60:
        return
    
    self._last_recon_time = time.time()
    
    try:
        # Get all open orders from exchange
        orders_response = self.delta_client.get_orders(
            product_id=self.product_id,
            state='open'
        )
        
        if orders_response.get('success'):
            open_orders = orders_response.get('result', [])
            
            # Filter BUY orders
            buy_orders = [o for o in open_orders if o.get('side') == 'buy']
            
            # Check for orphans
            with self._state_lock:
                tracked_order_id = self.pending_buy.get('order_id') if self.pending_buy else None
            
            for order in buy_orders:
                order_id = str(order.get('id'))
                if order_id != tracked_order_id:
                    log.critical(f"🚨 ORPHAN ORDER DETECTED: {order_id} @ ${order.get('limit_price')}")
                    log.critical(f"   Not tracked in pending_buy - cancelling...")
                    # Cancel orphan
                    self.delta_client.cancel_order(order_id, self.product_id)
    
    except Exception as e:
        log.error(f"Order reconciliation failed: {e}")
```

---

## 📋 SUMMARY

**Guardian Status Issue**: ✅ **FIXED**
- Path mismatch resolved
- Backend restarted
- Guardian now shows as running

**Duplicate BUY Orders**: ⚠️ **NEEDS INVESTIGATION**
- 2 orders at $109,000 (8 minutes apart)
- Violates "single pending buy" design
- Need to check if both filled (over-leverage risk)

**Last 4 Orders**:
1. TP order @ $108,287.50 ✅
2. BUY @ $106,287.50 (failed to cancel during halt) ⚠️
3. BUY @ $109,000 (#1) 🔴
4. BUY @ $109,000 (#2) DUPLICATE 🔴

**Action Required**:
1. ✅ Guardian status - FIXED, refresh browser
2. 🔴 Check exchange for orders 1015075838 and 1015081634
3. 🔴 Apply duplicate price check
4. 🔴 Add orphan order reconciliation

---

**Session**: October 31, 2025  
**Status**: Guardian display fixed, duplicate orders under investigation

