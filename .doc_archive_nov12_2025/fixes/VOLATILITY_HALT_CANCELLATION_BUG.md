# 🚨 VOLATILITY HALT - ORDER CANCELLATION FAILURE

**Issue**: When volatility becomes unsafe, pending BUY orders are NOT being cancelled on the exchange  
**Date**: October 31, 2025  
**Impact**: Orders execute during volatile conditions despite halt being triggered  
**Severity**: 🔴 **CRITICAL** - Defeats purpose of volatility protection

---

## 🔍 ROOT CAUSE ANALYSIS

### **The Smoking Gun** 🔫

From your bot logs:
```
2025-10-31 02:17:15,577 [WARNING] 🌊 VOLATILITY HALT TRIGGERED
2025-10-31 02:17:15,577 [INFO] 🗑️  Cancelling pending BUY @ 106287.5 (Order ID: 1014484029)
2025-10-31 02:17:16,531 [WARNING] ⚠️ Error cancelling pending BUY: 400 Client Error: Bad Request
2025-10-31 02:17:16,531 [INFO] 🗑️  Cancelled pending BUY @ $106,288  ⬅️ FALSE POSITIVE!
```

**What Happened**:
1. ✅ Volatility halt triggered correctly
2. ✅ Attempted to cancel order 1014484029
3. ❌ Exchange API returned **400 Bad Request** error
4. ⚠️  Bot **logged "Cancelled"** anyway (false positive!)
5. ❌ Order likely **STILL ACTIVE** on exchange
6. ❌ Bot thinks it's safe, but order could fill during volatility

---

## 💥 THE BUG IN CODE

### **Location**: `bot/strategy/gbot_ws.py` lines 1187-1233

```python
def _cancel_pending_buy(self) -> bool:
    """Cancel existing pending buy order if it exists"""
    # ... get order details ...
    
    try:
        log.info(f"🗑️  Cancelling pending BUY @ {_fmt_px(order_price)} (Order ID: {order_id})")
        resp = self.delta_client.cancel_order(order_id=order_id, product_id=int(self.product_id))
        
        if not resp.get('success'):
            log.warning(f"⚠️ Cancel response: {resp}")  # ⬅️ Only a WARNING!
        
        # ❌ CONTINUES ANYWAY even if cancel failed!
        
        # Wait for WS confirmation (2 seconds)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            with self._state_lock:
                still_same = self.pending_buy and self.pending_buy.get('order_id') == order_id
            if not still_same:
                break
            time.sleep(0.1)
        
        # ✅ Clear local state (even if API failed!)
        with self._state_lock:
            if self.pending_buy and self.pending_buy.get('order_id') == order_id:
                self.pending_buy = None  # ⬅️ CLEARED DESPITE FAILURE!
        return True  # ⬅️ Returns SUCCESS even when it failed!
        
    except Exception as e:
        log.warning(f"⚠️ Error cancelling pending BUY: {e}")
        
        # ❌ CRITICAL BUG: "Last resort" clears state WITHOUT verifying exchange
        with self._state_lock:
            self.pending_buy = None  # ⬅️ Order might still be on exchange!
        return False  # At least returns False, but damage done
```

**The Problem**: 
- **Optimistic Cleanup**: Bot clears local state even when exchange API fails
- **False Success**: Returns `True` even when cancellation didn't work
- **No Verification**: Never checks if order actually cancelled on exchange
- **Dangerous Assumption**: Assumes WS will be "source of truth" but WS might not update

---

## 🎯 WHY 400 BAD REQUEST?

### **Possible Reasons**:

1. **Order Already Filled** (Most Likely)
   - Order filled microseconds before cancel attempt
   - Exchange rejects: "Cannot cancel filled order"
   - Bot should detect fill, not just clear state

2. **Order Already Cancelled**
   - Previous cancel attempt succeeded
   - Duplicate cancel request rejected
   - Rare but possible in concurrent scenarios

3. **Invalid Order ID**
   - Order ID format issue
   - API endpoint expects different format
   - Less likely given other operations work

4. **Rate Limiting / API Error**
   - Exchange temporarily rejecting requests
   - Transient error that should retry
   - Currently NO retry logic

---

## 📊 IMPACT ANALYSIS

### **Real-World Consequence**

**Scenario from Your Logs**:
```
02:17:15 - IV becomes 43.7% (> 30% limit) → HALT triggered
02:17:15 - Try to cancel order 1014484029 @ $106,287.5
02:17:16 - API returns 400 error
02:17:16 - Bot logs "Cancelled" and clears local state
02:17:16 - Order 1014484029 likely STILL ACTIVE on exchange!
```

**If order fills**:
- ✅ Position opened despite volatility halt
- ❌ No TP order placed (halt blocked new orders)
- ❌ UNPROTECTED POSITION during high volatility
- ❌ Violates entire purpose of volatility protection

### **Safety Violation Cascade**

```
Volatility Unsafe
    ↓
Halt Triggered
    ↓
Cancel Order (FAILS)
    ↓
Bot thinks cancelled
    ↓
Order still active
    ↓
Order FILLS
    ↓
No TP placed (halt active)
    ↓
Unprotected position
    ↓
High volatility + No protection = 💥
```

---

## 🔧 THE FIX REQUIRED

### **Fix #1: Verify Cancellation Success**

```python
def _cancel_pending_buy(self) -> bool:
    """
    Cancel existing pending buy order with verification
    
    ✅ FIXED: Verifies cancellation actually worked before clearing state
    """
    with self._state_lock:
        pb = self.pending_buy
    if not pb:
        return True

    order_id = pb.get('order_id')
    client_id = pb.get('client_order_id')
    order_price = pb.get('price')

    try:
        log.info(f"🗑️  Cancelling pending BUY @ {_fmt_px(order_price)} (Order ID: {order_id})")
        resp = self.delta_client.cancel_order(order_id=order_id, product_id=int(self.product_id))
        
        # ✅ CHECK: Did cancellation succeed?
        if not resp.get('success'):
            error_code = resp.get('error', {}).get('code', '')
            error_msg = resp.get('error', {}).get('message', 'Unknown error')
            
            # Handle specific errors
            if 'already filled' in error_msg.lower() or 'filled' in error_code.lower():
                log.warning(f"⚠️  Order already filled - will be processed by fill handler")
                # Don't clear state - let fill handler process it
                return False
            elif 'not found' in error_msg.lower() or 'cancelled' in error_msg.lower():
                log.info(f"✅ Order already cancelled or not found")
                # Safe to clear state
            else:
                # Unknown error - be conservative
                log.error(f"❌ Cancel failed: {error_msg}")
                return False  # ⬅️ Return FALSE, don't clear state
        
        # ✅ VERIFY: Wait for confirmation from exchange
        verified = self._verify_order_cancelled(order_id, timeout=3.0)
        
        if not verified:
            log.error(f"❌ CRITICAL: Cancel not verified after 3s!")
            log.error(f"   Order {order_id} may still be active on exchange!")
            # ⚠️  Don't clear state - order might still fill
            return False
        
        # ✅ SAFE: Cancellation verified, clear state
        log.info(f"✅ Order cancellation verified by exchange")
        with self._state_lock:
            if self.pending_buy and self.pending_buy.get('order_id') == order_id:
                self.pending_buy = None
            if client_id:
                self._active_client_ids.discard(client_id)
        return True
        
    except Exception as e:
        log.error(f"❌ Exception during cancel: {e}")
        import traceback
        log.error(traceback.format_exc())
        
        # ⚠️  DON'T clear state on exception
        # Let operator manually verify order status
        return False
```

### **Fix #2: Add Verification Helper**

```python
def _verify_order_cancelled(self, order_id: str, timeout: float = 3.0) -> bool:
    """
    Verify order was actually cancelled on the exchange
    
    Args:
        order_id: Order ID to verify
        timeout: Maximum wait time for verification
        
    Returns:
        True if order confirmed cancelled/filled, False if still active
    """
    deadline = time.time() + timeout
    
    while time.time() < deadline:
        try:
            # Query current order status from exchange
            order_status = self.delta_client.get_order(order_id)
            
            if order_status.get('success'):
                result = order_status.get('result', {})
                state = result.get('state', '').lower()
                
                if state in ['cancelled', 'filled', 'rejected']:
                    log.debug(f"✅ Order {order_id} confirmed {state}")
                    return True
                elif state in ['open', 'pending']:
                    log.debug(f"⚠️  Order {order_id} still {state}")
                    # Continue waiting
                else:
                    log.warning(f"⚠️  Unknown order state: {state}")
            else:
                log.warning(f"⚠️  Failed to get order status")
        
        except Exception as e:
            log.debug(f"Error verifying order: {e}")
        
        time.sleep(0.3)
    
    # Timeout - couldn't verify
    log.error(f"❌ Timeout: Could not verify order {order_id} cancelled")
    return False
```

### **Fix #3: Handle Cancellation Failure in Halt**

```python
def _trigger_volatility_halt(self, reason: str, vol_tracker, target_price: float = None):
    """Triggered when volatility exceeds limits"""
    # ... existing code ...
    
    # Cancel the order with verification
    if self.pending_buy:
        order_info = {
            'price': self.pending_buy['price'],
            'order_id': self.pending_buy['order_id'],
            # ...
        }
        
        # ✅ CHECK: Did cancellation succeed?
        cancel_success = self._cancel_pending_buy()
        
        if cancel_success:
            state['cancelled_orders'].append(order_info)
            log.info(f"✅ Cancelled pending BUY @ ${order_info['price']:,.0f}")
        else:
            # ❌ CRITICAL: Cancellation failed!
            log.critical("=" * 70)
            log.critical("🚨 CRITICAL: ORDER CANCELLATION FAILED!")
            log.critical("=" * 70)
            log.critical(f"   Order ID: {order_info['order_id']}")
            log.critical(f"   Price: ${order_info['price']:,.0f}")
            log.critical(f"   This order may still be ACTIVE on exchange!")
            log.critical(f"   If it fills, position will be UNPROTECTED!")
            log.critical("=" * 70)
            
            # ⚠️  Mark as failed cancellation
            order_info['cancellation_failed'] = True
            order_info['requires_manual_check'] = True
            state['cancelled_orders'].append(order_info)
            
            # ✅ Send emergency alert
            try:
                from bot.utils.notifier import send_telegram_message
                message = (
                    f"🚨 CRITICAL: ORDER CANCELLATION FAILED!\n\n"
                    f"Volatility halt triggered but order still active:\n"
                    f"• Order ID: {order_info['order_id']}\n"
                    f"• Price: ${order_info['price']:,.0f}\n"
                    f"• Status: May still fill!\n\n"
                    f"⚠️  MANUAL ACTION REQUIRED:\n"
                    f"1. Check order status on Delta Exchange\n"
                    f"2. Manually cancel if still active\n"
                    f"3. Monitor for fill and place TP if needed\n"
                )
                send_telegram_message(message)
            except Exception as e:
                log.error(f"Failed to send emergency notification: {e}")
    
    # ... rest of halt logic ...
```

---

## ⚡ IMMEDIATE ACTIONS REQUIRED

### **1. Check Your Current Orders** (URGENT)

```bash
# Check if order 1014484029 is still active
curl -X GET "https://api.india.delta.exchange/v2/orders/1014484029" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Look for**:
- `"state": "open"` → Order still active! Need to cancel manually
- `"state": "filled"` → Order filled, check if TP order exists
- `"state": "cancelled"` → False alarm, already cancelled

### **2. Verify Recent Positions**

Check your Delta Exchange account for any:
- Positions opened around 02:17 AM
- Positions without TP orders
- Unexpected entries during volatility halt

### **3. Manual Verification Steps**

1. **Check Order 1014484029**:
   - If still open → Cancel immediately
   - If filled → Verify TP order exists, place manually if missing

2. **Check WebUI Positions Panel**:
   - Count positions shown
   - Verify all have TP orders
   - Look for unprotected entries

---

## 📋 IMPLEMENTATION CHECKLIST

- [ ] **Fix #1**: Add verification to `_cancel_pending_buy()`
- [ ] **Fix #2**: Implement `_verify_order_cancelled()` helper
- [ ] **Fix #3**: Handle cancellation failure in `_trigger_volatility_halt()`
- [ ] **Test**: Simulate cancellation failure scenario
- [ ] **Test**: Verify emergency notifications work
- [ ] **Deploy**: Apply fixes to production

---

## 🎯 PREVENTION STRATEGY

### **Add Periodic Order Reconciliation**

```python
def _reconcile_pending_orders(self):
    """
    Periodic check: Verify local state matches exchange reality
    Run every 60 seconds
    """
    with self._state_lock:
        if not self.pending_buy:
            return
        
        order_id = self.pending_buy['order_id']
    
    try:
        # Query exchange for order status
        status = self.delta_client.get_order(order_id)
        if status.get('success'):
            state = status['result'].get('state', '').lower()
            
            if state in ['cancelled', 'filled', 'rejected']:
                # Order not pending anymore
                log.warning(f"⚠️  DESYNC: Local shows pending, exchange shows {state}")
                log.warning(f"   Clearing local state to match exchange")
                
                with self._state_lock:
                    self.pending_buy = None
    
    except Exception as e:
        log.debug(f"Reconciliation check failed: {e}")
```

---

## 📊 SUMMARY

**Root Cause**: Optimistic cleanup - bot clears local state even when exchange API fails

**Impact**: Orders remain active during volatility halts, defeating safety mechanism

**Proof**: Log shows "400 Bad Request" but bot logs "Cancelled" anyway

**Risk**: Unprotected positions opened during high volatility

**Priority**: 🔴 **CRITICAL** - Fix before next trading session

**Related Issues**:
- Similar to TP placement failure (both involve false success logging)
- Part of broader pattern: insufficient exchange verification

---

**Analysis Completed**: October 31, 2025  
**Analyst**: AI Code Auditor  
**Next Steps**: 
1. Check order 1014484029 status immediately
2. Apply verification fixes
3. Test cancellation with simulated failures

