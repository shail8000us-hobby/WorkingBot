# ✅ PARTIAL FILL TESTING CHECKLIST

**Implementation Date:** November 8, 2025  
**Status:** ✅ Code Complete, Ready for Testing

---

## 📋 **PRE-TESTING VERIFICATION**

### ✅ **Simulation Test Results**
```
✅ Logic verified with test_partial_fill.py
✅ Fill 1 (10 lots): Position created, TP placed, pending_buy active
✅ Fill 2 (47 lots): Position created, TP placed, pending_buy active  
✅ Fill 3 (43 lots): Position created, TP placed, pending_buy cleared, next order placed
✅ Edge cases tested: duplicates, cancellations, extreme partials
```

### ✅ **Code Quality Checks**
```
✅ No syntax errors in ws_manager.py
✅ No syntax errors in gridbot.py
✅ Proper error handling implemented
✅ Comprehensive logging added
✅ Documentation complete
```

---

## 🧪 **TESTING PHASES**

### **Phase 1: DEMO Mode Testing** (Recommended First)

#### **Setup:**
```bash
# 1. Ensure demo mode is configured
grep "MODE=demo" grid_config.env

# 2. Set small lot size for testing
# Edit grid_config.env: LOT_SIZE=10

# 3. Start bot in demo mode
./bot_launcher.py
```

#### **Test Steps:**
1. ✅ Bot starts successfully
2. ✅ Place initial BUY order (10 lots)
3. ✅ Manually fill order in 3 parts via Delta Exchange demo:
   - Fill 3 lots → Check logs
   - Fill 4 lots → Check logs
   - Fill 3 lots → Check logs
4. ✅ Verify behavior matches expectations

#### **Expected Logs:**
```
⏳ PARTIAL FILL: buy +3 lots @ avg $105,000 | Total: 3/10 (30.0%) [order: X]
✅ BUY incremental fill: 3 lots @ $105,000
🛡️ TP placed: 3 lots @ $105,500
⏳ Order X still filling (3/10 lots) - waiting for more fills...

⏳ PARTIAL FILL: buy +4 lots @ avg $105,002 | Total: 7/10 (70.0%) [order: X]
✅ BUY incremental fill: 4 lots @ $105,002
🛡️ TP placed: 4 lots @ $105,502
⏳ Order X still filling (7/10 lots) - waiting for more fills...

🎯 FINAL FILL: buy +3 lots @ avg $105,005 | Total: 10/10 (100%) [order: X]
✅ BUY incremental fill: 3 lots @ $105,005
🛡️ TP placed: 3 lots @ $105,505
✅ Order X FULLY FILLED (10/10 lots) - placing next grid order
📍 Placing next grid BUY @ $104,500
```

#### **Verification Checklist:**
- [ ] Each partial fill creates separate position
- [ ] Each partial fill gets its own TP order
- [ ] Position sizes match incremental fills (3, 4, 3 lots)
- [ ] TP prices calculated from each fill's avg price
- [ ] pending_buy remains active until final fill
- [ ] Next grid order placed only after 100% filled
- [ ] No duplicate position creation
- [ ] No missing TP orders

---

### **Phase 2: LIVE Small Order Testing**

#### **Setup:**
```bash
# 1. Switch to live mode
# Edit grid_config.env: MODE=live

# 2. Use VERY small lot size
# Edit grid_config.env: LOT_SIZE=10  # Or smallest allowed

# 3. Start bot
./bot_launcher.py
```

#### **Test Scenarios:**

**Scenario 1: Market Order (High Liquidity)**
```
- Place 10-lot market order
- Market likely fills instantly (may not partial)
- Verify single fill handled correctly
```

**Scenario 2: Limit Order (Lower Liquidity)**
```
- Place 10-lot limit order slightly away from market
- Wait for partial fills as price moves through level
- Monitor each partial fill
```

**Scenario 3: Large Order (Guaranteed Partials)**
```
- Place 100-lot limit order (if budget allows)
- High probability of multiple partial fills
- Best test case for full validation
```

#### **Live Testing Checklist:**
- [ ] Bot handles single fill correctly (backward compatible)
- [ ] Bot handles 2-3 partial fills correctly
- [ ] Bot handles 5+ partial fills correctly
- [ ] WebSocket disconnection during partial doesn't break
- [ ] Reconciliation during partial doesn't duplicate
- [ ] Order cancellation during partial handled correctly
- [ ] All TPs placed successfully
- [ ] No API errors from multiple TP placements
- [ ] Position tracking accurate
- [ ] Next grid order timing correct

---

### **Phase 3: Stress Testing**

#### **Extreme Scenarios:**

**Test 1: High-Frequency Partials**
```
- Place large order (500+ lots) in high volatility
- Expect 10-20 partial fills
- Verify bot doesn't lag or crash
- Verify all TPs placed
```

**Test 2: WebSocket Interruption**
```
- Place order, get 2 partial fills
- Disconnect WebSocket manually
- Verify REST polling catches remaining fills
- Verify no duplicate positions
```

**Test 3: Reconciliation Stress**
```
- Place order, get partial fill
- Trigger manual reconciliation
- Verify pending_buy not cleared
- Verify no duplicate orders
```

**Test 4: Rapid Order Placement**
```
- Enable high grid count
- Let multiple orders fill partially simultaneously
- Verify separate tracking per order
- Verify no cross-contamination
```

---

## 📊 **MONITORING DASHBOARD**

### **Key Metrics to Watch:**

```bash
# Monitor logs in real-time
tail -f bot_live.log | grep -E "PARTIAL FILL|FINAL FILL|FULLY FILLED"

# Check position count
# Should match number of partial fills, not number of orders
cat runtime_state.json | jq '.open_tranches | length'

# Check TP count
# Should equal position count
cat runtime_state.json | jq '.open_tranches[] | .tp_id' | wc -l

# Check for errors
tail -100 bot_live.log | grep -i error
```

### **WebUI Monitoring:**
```
- Open WebUI: http://localhost:8080
- Navigate to Positions panel
- Verify multiple positions from same order_id
- Check each position has TP order
- Verify sizes are incremental (not full order size)
```

---

## 🚨 **TROUBLESHOOTING**

### **Issue 1: All fills processed as complete**
**Symptoms:** Every partial fill places next grid order  
**Cause:** `is_complete` flag not working  
**Fix:** Check WebSocket data has `unfilled_size` field

### **Issue 2: Only first fill processed**
**Symptoms:** Subsequent fills ignored  
**Cause:** Old deduplication logic still active  
**Fix:** Verify ws_manager.py changes applied correctly

### **Issue 3: Position sizes wrong**
**Symptoms:** All positions show full order size  
**Cause:** Using `self.lot` instead of `fill_data['fill_size']`  
**Fix:** Verify gridbot.py handler changes applied

### **Issue 4: Multiple next grid orders**
**Symptoms:** Grid order placed on every partial  
**Cause:** `is_complete` check missing  
**Fix:** Verify `if is_complete:` block in handlers

### **Issue 5: Memory leak**
**Symptoms:** `_order_fill_tracking` dict grows infinitely  
**Cause:** Cleanup not running  
**Fix:** Verify cleanup code executes on order complete

---

## ✅ **ACCEPTANCE CRITERIA**

Mark test as PASSED when ALL are true:

### **Functional Requirements:**
- [ ] Each partial fill creates independent position
- [ ] Each partial fill gets its own TP order
- [ ] Position sizes are incremental (match actual fill size)
- [ ] TP prices calculated from each fill's average price
- [ ] pending_buy/sell stays active until order 100% filled
- [ ] Next grid order placed only when is_complete=True
- [ ] No duplicate positions from same fill
- [ ] No missing TP orders

### **Performance Requirements:**
- [ ] No API rate limit errors from multiple TPs
- [ ] No memory leaks from tracking dict
- [ ] No lag during rapid partial fills
- [ ] WebSocket processing <50ms per fill
- [ ] TP placement <200ms per fill

### **Reliability Requirements:**
- [ ] Handles WebSocket disconnection gracefully
- [ ] Survives reconciliation during partial fills
- [ ] Handles order cancellation mid-fill
- [ ] Handles duplicate WebSocket messages
- [ ] No crashes under stress

### **Monitoring Requirements:**
- [ ] Clear logs for each partial fill
- [ ] Clear logs for order completion
- [ ] Easy to track fill progress
- [ ] Position tracking accurate in runtime_state.json
- [ ] WebUI shows correct position sizes

---

## 📝 **TEST RESULTS LOG**

### **Test Run 1: Demo Mode** (Date: _______)
```
Order Size: _____ lots
Partial Fills: _____ fills
Result: ✅ PASS / ❌ FAIL
Notes: 
```

### **Test Run 2: Live Small Order** (Date: _______)
```
Order Size: _____ lots
Partial Fills: _____ fills
Result: ✅ PASS / ❌ FAIL
Notes:
```

### **Test Run 3: Live Large Order** (Date: _______)
```
Order Size: _____ lots
Partial Fills: _____ fills
Result: ✅ PASS / ❌ FAIL
Notes:
```

---

## 🚀 **DEPLOYMENT DECISION**

### **GREEN LIGHT (Deploy to Production):**
- ✅ All demo tests passed
- ✅ Small live order test passed
- ✅ No errors in logs
- ✅ Position tracking accurate
- ✅ TP placement 100% successful
- ✅ Stress tests passed

### **YELLOW LIGHT (More Testing Needed):**
- ⚠️ Minor issues found but not critical
- ⚠️ Need more real-world data
- ⚠️ Edge cases need investigation

### **RED LIGHT (Do Not Deploy):**
- 🚨 Duplicate positions created
- 🚨 Missing TP orders
- 🚨 Next grid orders placed incorrectly
- 🚨 Memory leaks detected
- 🚨 Bot crashes or errors

---

## 📞 **SUPPORT CONTACTS**

If critical issues found:
1. Stop the bot immediately
2. Save logs: `cp bot_live.log bot_live_partial_fill_error.log`
3. Save state: `cp runtime_state.json runtime_state_error.json`
4. Review error logs
5. Revert to previous version if needed

---

**Remember:** Start small (10-lot demo order) and gradually increase to full production loads.

**Testing Status:** ⏳ PENDING - Ready to begin Phase 1
