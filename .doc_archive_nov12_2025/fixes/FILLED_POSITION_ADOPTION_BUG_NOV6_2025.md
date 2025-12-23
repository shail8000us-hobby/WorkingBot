# Filled Position Adoption Bug - November 6, 2025

## 🐛 Problem Summary

Bot successfully places and fills BUY orders but **fails to adopt filled positions on restart**. This causes the bot to place DUPLICATE orders at the same price instead of managing the filled position.

---

## 📊 Current Behavior

### What Happens:
1. ✅ Bot places Strict Grid BUY @ $102,900 (Order ID: earlier)
2. ✅ Order fills on exchange → 1 BTC LONG @ $102,900
3. ❌ Bot restarts (or reconnects)
4. ⚠️ Detects filled position: "Exchange position not in local state"
5. ❌ Does NOT adopt the position into local state
6. ❌ Shows "Positions: 0/10" (incorrect - should be 1/10)
7. ❌ Places NEW BUY @ $102,900 (Order ID: 2147819771)
8. ❌ Never places TP @ $103,200 for the filled position
9. ❌ Never places next BUY @ $102,600

### Log Evidence:
```
2025-11-06 17:07:59 [WARNING] ⚠️ Exchange position not in local state: 
    {'entry_price': '102900.00000000', 'product_id': 84, 'product_symbol': 'BTCUSD', 'size': 1}
2025-11-06 17:07:59 [INFO] ✅ Reconciliation complete: 0 local, 1 exchange, 0 orphaned
2025-11-06 17:08:00 [INFO] ✅ Got price: $103,098
2025-11-06 17:08:00 [INFO] 🔄 Reconciling orphaned orders from exchange...
2025-11-06 17:08:01 [INFO] ✅ No orphaned bot BUY orders found on exchange
2025-11-06 17:08:01 [INFO] ✅ Strict Grid: Placing BUY @ $102,900.00 (MAKER order)
2025-11-06 17:08:02 [INFO] ✅ BUY order placed: ID 2147819771
...
2025-11-06 17:08:12 [INFO] [HB] Positions: 0/10, Price: $103,107
```

**Key Issue**: "0 orphaned" reported but 1 filled position detected on exchange!

---

## 🔍 Root Cause

### Missing Adoption Logic

**Current Code Flow:**
1. **reconciliation.py** (lines 156-166):
   - Detects exchange positions
   - Compares with local positions
   - Logs warning if not found locally
   - **DOES NOT add to orphaned list** (bug!)

2. **gridbot.py** `_reconcile_orphaned_orders()` (lines 777-866):
   - Only checks for **orphaned ORDERS** (open BUY orders)
   - Uses `list_orders(state="open")` - only finds pending orders
   - **Does NOT check for filled positions**
   - Cannot adopt positions that have already filled

### Why It Fails:
- Position @ $102,900 **already filled** → No open order exists
- `_reconcile_orphaned_orders()` queries `state="open"` → Returns empty
- Bot says "No orphaned bot BUY orders found" → Correct! (but position still orphaned)
- Bot proceeds to startup logic → Places NEW order at $102,900
- **Result**: Duplicate exposure risk + original position unmanaged

---

## ✅ Proposed Fix

### Solution 1: Add Filled Position Adoption

Add a new function `_adopt_filled_positions()` to run after `_reconcile_orphaned_orders()`:

```python
def _adopt_filled_positions(self):
    """
    Adopt filled positions from exchange that are not in local state
    
    This handles the case where:
    1. Bot placed a BUY order
    2. Order filled on exchange
    3. Bot restarted before processing the fill event
    4. Position exists on exchange but not in local state
    """
    try:
        log.info("🔄 Checking for filled positions to adopt...")
        
        # Get current positions from exchange
        positions_response = self.delta_client.get_positions(product_id=self.product_id)
        
        if not positions_response.get('success'):
            log.warning(f"⚠️ Failed to query positions: {positions_response}")
            return
        
        exchange_positions = positions_response.get('result', [])
        
        # Filter for non-zero positions
        for ex_pos in exchange_positions:
            size = ex_pos.get('size', 0)
            if size == 0:
                continue  # Skip closed positions
            
            entry_price = float(ex_pos.get('entry_price', 0))
            product_symbol = ex_pos.get('product_symbol', '')
            
            # Check if we have this position in local state
            found_local = False
            for local_tranche in self.position_mgr.get_open_tranches():
                if abs(local_tranche.get('entry', 0) - entry_price) < 1:
                    found_local = True
                    break
            
            if not found_local:
                log.warning(f"⚠️ Found filled position not in local state:")
                log.warning(f"   Entry: ${entry_price:,.0f}, Size: {size}, Symbol: {product_symbol}")
                
                # Adopt the position
                tranche_id = self.position_mgr.add_tranche({
                    'entry': entry_price,
                    'size': size,
                    'entry_time': time.time(),
                    'product_id': self.product_id,
                    'adopted': True  # Mark as adopted from exchange
                })
                
                log.info(f"✅ Adopted filled position into local state: Tranche {tranche_id}")
                
                # Calculate TP level
                tp_price = entry_price + self.grid_step
                
                # Place TP order
                tp_order_id = self.order_mgr.place_sell_order(tp_price, reduce_only=True)
                
                if tp_order_id:
                    self.position_mgr.link_tranche_to_tp(tranche_id, tp_order_id)
                    log.info(f"🛡️ TP order placed @ ${tp_price:,.0f} for adopted position")
                else:
                    log.error(f"❌ Failed to place TP for adopted position @ ${entry_price:,.0f}")
                
                # Place next BUY order (if within capacity)
                capacity = self.position_mgr.get_capacity()
                if capacity['open'] < capacity['max_open']:
                    next_buy_price = entry_price - self.grid_step
                    
                    # Only place if within grid bounds
                    if next_buy_price >= self.lower_bound:
                        next_buy_id = self.order_mgr.place_buy_order(next_buy_price)
                        
                        if next_buy_id:
                            self.position_mgr.set_pending_buy({
                                'order_id': next_buy_id,
                                'price': next_buy_price,
                                'timestamp': time.time()
                            })
                            log.info(f"📝 Next BUY placed @ ${next_buy_price:,.0f}")
                    else:
                        log.info(f"⚠️ Next BUY @ ${next_buy_price:,.0f} below lower bound ${self.lower_bound:,.0f}")
        
    except Exception as e:
        log.error(f"❌ Error adopting filled positions: {e}")
        import traceback
        log.error(traceback.format_exc())
```

### Integration:

**gridbot.py** `run()` method (around line 1003):
```python
# After WebSocket connects and price received
if self.current_price:
    # Reconcile orphaned pending orders
    self._reconcile_orphaned_orders()
    
    # NEW: Adopt filled positions not in local state
    self._adopt_filled_positions()
    
    # Continue with normal startup...
```

---

## 🎯 Expected Behavior After Fix

### Startup Flow:
1. ✅ Bot restarts, connects to WebSocket
2. ✅ Detects exchange position @ $102,900
3. ✅ **Adopts position into local state** (new tranche)
4. ✅ **Places TP @ $103,200** for adopted position
5. ✅ **Places next BUY @ $102,600** (continuing the grid)
6. ✅ Shows "Positions: 1/10" (correct count)
7. ✅ Normal grid operation resumes

### Log Output:
```
2025-11-06 XX:XX:XX [INFO] 🔄 Checking for filled positions to adopt...
2025-11-06 XX:XX:XX [WARNING] ⚠️ Found filled position not in local state:
2025-11-06 XX:XX:XX [WARNING]    Entry: $102,900, Size: 1, Symbol: BTCUSD
2025-11-06 XX:XX:XX [INFO] ✅ Adopted filled position into local state: Tranche 1
2025-11-06 XX:XX:XX [INFO] 🛡️ TP order placed @ $103,200 for adopted position
2025-11-06 XX:XX:XX [INFO] 📝 Next BUY placed @ $102,600
2025-11-06 XX:XX:XX [INFO] [HB] Positions: 1/10, Price: $103,107
```

---

## 🧪 Testing Plan

### Test Scenario:
1. Cancel current duplicate order (ID: 2147819771)
2. Implement `_adopt_filled_positions()` function
3. Restart bot
4. Verify position @ $102,900 adopted
5. Verify TP @ $103,200 placed
6. Verify next BUY @ $102,600 placed
7. Verify "Positions: 1/10" shown correctly

### Validation Criteria:
- [ ] Filled position adopted into local state
- [ ] TP order placed for adopted position
- [ ] Next BUY order placed correctly
- [ ] No duplicate orders at same price
- [ ] Position count accurate (1/10, not 0/10)
- [ ] Grid ladder continues normally

---

## 📝 Related Issues

### Connection to Original Bug Report:
**User's Original Issue**: "bot has executed buy order but failed to place tp order and new lower buy order"

**Actual Sequence**:
1. Bot placed BUY @ $102,900 (Strict Grid)
2. Order filled successfully
3. **Reconciliation bug**: Cancelled the order 10 seconds later (FIXED Nov 6)
4. Bot never received fill event (WebSocket timing)
5. **Position adoption bug**: Bot doesn't adopt filled positions on restart (THIS BUG)
6. Result: No TP placed, no next BUY placed

**Fixes Implemented**:
1. ✅ **Reconciliation Fix**: Added `strict_grid_order` flag to prevent cancellation
2. ✅ **WebSocket Fallback**: Added REST API fallback with 30s timeout
3. ⏳ **Position Adoption**: Need to implement `_adopt_filled_positions()` (THIS FIX)

---

## 🚀 Implementation Priority

**CRITICAL - HIGH PRIORITY**

This bug causes:
- **Position Risk**: Filled positions left unmanaged (no TP protection)
- **Duplicate Orders**: Bot places new orders at same price (double exposure)
- **Grid Failure**: Grid ladder doesn't advance (no next BUY placed)
- **State Corruption**: Position count incorrect (shows 0 when should be 1)

**Immediate Action**: Implement `_adopt_filled_positions()` before next restart.

---

## 📊 Status

- **Identified**: November 6, 2025 @ 17:10 IST
- **Root Cause**: Missing filled position adoption logic
- **Solution**: Add `_adopt_filled_positions()` function
- **Implementation**: PENDING
- **Testing**: PENDING
- **Validation**: PENDING

---

## 🔗 Related Files

- `bot/strategy/gridbot.py` (lines 777-866): `_reconcile_orphaned_orders()`
- `bot/strategy/modules/reconciliation.py` (lines 156-166): Position detection
- `bot/strategy/modules/position_manager.py`: Tranche management
- `STRICT_GRID_RECONCILIATION_FIX_NOV6_2025.md`: Related fix documentation

---

## 💡 Future Improvements

1. **Unified Reconciliation**: Combine order adoption + position adoption into one function
2. **State Persistence**: Save filled positions to disk to survive restarts
3. **Fill Event Replay**: Re-process missed fill events from exchange history
4. **Sanity Checks**: Alert if exchange positions != local positions after reconciliation
5. **AUTO Resume Grid**: Automatically reconstruct entire grid ladder from exchange positions

---

**Document Version**: 1.0  
**Last Updated**: November 6, 2025 @ 17:15 IST  
**Author**: Gridbot System  
**Status**: 🚨 **CRITICAL BUG - NEEDS IMMEDIATE FIX**
