# Delta Exchange Order Cancellation Analysis Report

## Executive Summary

**Date:** November 18, 2025  
**Issue:** Bot failing to cancel order #1042368724 with 404 errors  
**Root Cause Identified:** ✅ YES - API endpoint mismatch  
**Solution Available:** ✅ YES - Delta Exchange provided correct implementation

---

## Critical Finding: API Endpoint Mismatch

### Delta Exchange Official Solution
According to Delta Exchange support, the correct cancellation endpoint is:

```
DELETE /v2/orders
Body: {"id": order_id, "product_id": 27}
```

### Our Current Implementation

**File:** `bot/api/async_delta_client.py` (Line 433-436)
```python
response = await self._request_with_retry(
    method="DELETE",
    path=f"/v2/orders/{order_id}"  # ❌ WRONG: ID in URL path
)
```

**File:** `bot/api/delta_client.py` (Line 594)
```python
return self._req("DELETE", f"/v2/orders/{int(order_id)}")  # ❌ WRONG: ID in URL path
```

### The Problem

| Aspect | Our Code | Delta Exchange Requirement |
|--------|----------|---------------------------|
| HTTP Method | DELETE ✅ | DELETE ✅ |
| Endpoint | `/v2/orders/{order_id}` ❌ | `/v2/orders` ✅ |
| Order ID Location | URL path ❌ | Request body ✅ |
| Product ID | Not sent ❌ | Required in body ✅ |

**This explains the 404 errors:** We're hitting the wrong endpoint format!

---

## Delta Exchange Recommended Logic

### 1. Position-Based Mode Detection
```python
# Get position to determine mode
position = get_position(product_id=27)
if position['size'] > 0:
    mode = "LONG"
elif position['size'] < 0:
    mode = "SHORT"
```

**Our Implementation:** ✅ CORRECT
- We already track mode in `self.mode` (LONG/SHORT)
- Set during bot initialization from config

### 2. Selective Cancellation Rules

**Delta Exchange Logic:**
- **LONG Mode:** Cancel pending BUY orders, preserve pending SELL orders (TPs)
- **SHORT Mode:** Cancel pending SELL orders, preserve pending BUY orders (TPs)
- **Always Preserve:** Orders with `reduce_only=True` (exit orders)

**Our Implementation:** ✅ PARTIALLY CORRECT

#### What We Do Right:
1. **Shutdown Cleanup** (`_cancel_pending_entry_orders_on_shutdown`):
   - Cancels pending BUY in LONG mode ✅
   - Cancels pending SELL in SHORT mode ✅
   - Preserves reduce_only orders ✅
   - Code: Lines 3720-3900 in `async_gridbot.py`

2. **Orphaned Order Reconciliation** (`_reconcile_orphaned_orders`):
   - Filters by `reduce_only=False` ✅
   - Only adopts entry orders, not TP orders ✅
   - Code: Lines 552-705 in `async_gridbot.py`

3. **2-Step Away Cancellation** (Saga):
   - Cancels BUY orders 2+ steps below TP ✅
   - Preserves TP orders (they're SELL orders in LONG mode) ✅
   - Code: Lines 425-476 in `fill_processing_saga.py`

#### What We're Missing:
1. **Startup Cleanup** (`_cleanup_misaligned_orders`):
   - ❌ Does NOT check `reduce_only` flag
   - ❌ Could accidentally cancel TP orders
   - Code: Lines 707-745 in `async_gridbot.py`

---

## Comparison Matrix

| Feature | Delta Solution | Our Bot | Status |
|---------|---------------|---------|--------|
| **API Endpoint** |
| Cancel endpoint | `/v2/orders` with body | `/v2/orders/{id}` in URL | ❌ WRONG |
| Product ID in body | Required | Not sent | ❌ MISSING |
| Order ID in body | Required | In URL path | ❌ WRONG |
| **Cancellation Logic** |
| Mode detection | From position size | From config | ✅ OK (different approach) |
| LONG: Cancel BUY | Yes | Yes | ✅ CORRECT |
| LONG: Preserve SELL | Yes | Yes | ✅ CORRECT |
| SHORT: Cancel SELL | Yes | Yes | ✅ CORRECT |
| SHORT: Preserve BUY | Yes | Yes | ✅ CORRECT |
| Check reduce_only | Yes | Partial | ⚠️ INCOMPLETE |
| **Safety Features** |
| Preserve TP orders | Yes (reduce_only) | Yes (shutdown only) | ⚠️ INCOMPLETE |
| Preserve executed positions | Yes | Yes | ✅ CORRECT |
| Dry-run mode | Yes | No | ❌ MISSING |
| Detailed logging | Yes | Yes | ✅ CORRECT |

---

## Specific Issues Found

### Issue 1: Wrong Cancel Endpoint ❌ CRITICAL
**Location:** `bot/api/async_delta_client.py:433-436`

**Current Code:**
```python
async def cancel_order(self, order_id: str) -> Dict[str, Any]:
    response = await self._request_with_retry(
        method="DELETE",
        path=f"/v2/orders/{order_id}"  # ❌ WRONG
    )
```

**Required Fix:**
```python
async def cancel_order(self, order_id: str, product_id: int) -> Dict[str, Any]:
    response = await self._request_with_retry(
        method="DELETE",
        path="/v2/orders",  # ✅ CORRECT
        json={"id": int(order_id), "product_id": product_id}  # ✅ Body params
    )
```

### Issue 2: Missing reduce_only Check in Startup Cleanup ⚠️ IMPORTANT
**Location:** `bot/strategy/async_gridbot.py:731-740`

**Current Code:**
```python
for order in open_orders:
    if order.get("side") == "buy" and order.get("state") == "open":
        order_price = float(order.get("limit_price", 0))
        order_id = str(order.get("id"))
        client_id = order.get("client_order_id", "")
        
        if client_id.startswith("GBOT_") and order_price < threshold:
            # ❌ MISSING: No reduce_only check!
            await self.order_actor.ask("CANCEL_ORDER", {"order_id": order_id})
```

**Required Fix:**
```python
for order in open_orders:
    if order.get("side") == "buy" and order.get("state") == "open":
        order_price = float(order.get("limit_price", 0))
        order_id = str(order.get("id"))
        client_id = order.get("client_order_id", "")
        is_reduce_only = order.get("reduce_only", False)  # ✅ ADD THIS
        
        # ✅ Skip TP orders (reduce_only)
        if is_reduce_only:
            continue
        
        if client_id.startswith("GBOT_") and order_price < threshold:
            await self.order_actor.ask("CANCEL_ORDER", {"order_id": order_id})
```

### Issue 3: Missing reduce_only Check in Saga ⚠️ IMPORTANT
**Location:** `bot/strategy/sagas/fill_processing_saga.py:443-456`

**Current Code:**
```python
for order in open_orders:
    if order.get("side") == "buy" and order.get("state") == "open":
        order_price = float(order.get("limit_price", 0))
        order_id = str(order.get("id"))
        
        if order_price <= two_steps_away:
            # ❌ MISSING: No reduce_only check!
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": order_id}, None, correlation_id)
            )
```

**Required Fix:**
```python
for order in open_orders:
    if order.get("side") == "buy" and order.get("state") == "open":
        order_price = float(order.get("limit_price", 0))
        order_id = str(order.get("id"))
        is_reduce_only = order.get("reduce_only", False)  # ✅ ADD THIS
        
        # ✅ Skip TP orders (reduce_only)
        if is_reduce_only:
            continue
        
        if order_price <= two_steps_away:
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": order_id}, None, correlation_id)
            )
```

---

## Why Order #1042368724 Cannot Be Cancelled

**Order Details:**
- ID: 1042368724
- Created: 2025-11-18T06:43:39 (12:13 PM IST)
- Price: $89,000
- Client ID: GBOT_BUY_89000_1763448219

**Cancellation Attempts:**
1. Verification (GET): ✅ Success - order found as "open"
2. Cancellation (DELETE): ❌ 404 Error

**Root Cause:**
- GET endpoint: `/v2/orders/{order_id}` ✅ Works
- DELETE endpoint we use: `/v2/orders/{order_id}` ❌ Wrong format
- DELETE endpoint required: `/v2/orders` with body ✅ Correct

The GET works because it uses the correct format for retrieval, but DELETE requires a different format with the order ID in the request body, not the URL path.

---

## What's Working Correctly

### ✅ Shutdown Cleanup
**File:** `async_gridbot.py:3720-3900`
- Correctly cancels pending BUY (LONG) or SELL (SHORT)
- Preserves reduce_only orders (TP orders)
- Has 12-second verification wait
- Detailed logging and error handling

### ✅ Orphaned Order Reconciliation
**File:** `async_gridbot.py:552-705`
- Filters out reduce_only orders
- Only adopts entry orders
- Handles multiple orphaned orders correctly

### ✅ Position Management
- Tracks positions correctly
- Maintains TP orders for protection
- Never touches manual positions

---

## Required Changes Summary

### Priority 1: CRITICAL - Fix Cancel Endpoint ❌
**Files to modify:**
1. `bot/api/async_delta_client.py` - Update `cancel_order()` method
2. `bot/api/delta_client.py` - Update `cancel_order()` method
3. All calling code - Add `product_id` parameter

**Impact:** Without this fix, NO order cancellations will work

### Priority 2: IMPORTANT - Add reduce_only Checks ⚠️
**Files to modify:**
1. `bot/strategy/async_gridbot.py` - `_cleanup_misaligned_orders()`
2. `bot/strategy/sagas/fill_processing_saga.py` - 2-step cancellation logic

**Impact:** Without this, bot might accidentally cancel TP orders

### Priority 3: NICE-TO-HAVE - Add Dry-Run Mode 💡
**Files to modify:**
1. `bot/strategy/async_gridbot.py` - Add dry-run flag to cleanup methods

**Impact:** Better testing and safety

---

## Testing Recommendations

### After Fixing Cancel Endpoint:
1. **Test with current stuck order:**
   - Restart bot
   - Verify order #1042368724 gets cancelled
   - Check no 404 errors in logs

2. **Test TP fill scenario:**
   - Wait for a TP to fill
   - Verify 2-step-away orders are cancelled
   - Verify new 1-step-away order is placed
   - Verify TP orders are NOT cancelled

3. **Test startup cleanup:**
   - Place test order 3+ steps away
   - Restart bot
   - Verify order is cancelled
   - Verify TP orders are preserved

### After Adding reduce_only Checks:
1. **Test with TP orders present:**
   - Have open positions with TP orders
   - Trigger cleanup
   - Verify TP orders are NOT cancelled
   - Verify only entry orders are cancelled

---

## Conclusion

**Main Problem:** Our cancel endpoint format doesn't match Delta Exchange API requirements.

**Solution:** Update `cancel_order()` methods to use `/v2/orders` endpoint with order ID and product ID in request body.

**Secondary Issue:** Missing `reduce_only` checks in startup cleanup and saga could accidentally cancel TP orders.

**Overall Assessment:** 
- Core logic is sound ✅
- Implementation has critical API mismatch ❌
- Safety checks need enhancement ⚠️

**Estimated Fix Time:** 30 minutes to update both API clients and add reduce_only checks.

**Risk Level:** LOW - Changes are isolated to API client methods and safety checks.
