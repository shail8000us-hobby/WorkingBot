# Testing Guide: Single Pending Order Fix

**Date:** December 11, 2025  
**Purpose:** Verify that the single pending order rule is now reliably enforced  
**Estimated Time:** 30-60 minutes of monitoring

---

## Pre-Test Checklist

- [ ] Bot is running (pm2 list shows gridbot-live is online)
- [ ] You have positions open with TPs set
- [ ] You can monitor bot logs in real-time
- [ ] You have access to Delta Exchange API or WebUI to check orders

---

## Test Method 1: Log Monitoring (Easiest)

### Step 1: Start Monitoring Logs

```bash
# Terminal 1: Watch bot logs
pm2 logs gridbot-live --lines 100

# Look for these patterns when a TP fills:
# ✅ [SAGA] Successfully canceled order #X @ $Y
# 📊 [SAGA] Cancellation summary: X succeeded, Y failed
```

### Step 2: Wait for a TP to Fill

When market moves and a TP fills, you should see:

**Expected Log Output (LONG Mode):**
```
[SAGA] TP filled @ 90000, placing new BUY @ 89500 (TP - 1 step)
[SAGA] SINGLE PENDING ORDER RULE: Cancelling bot order #12345 @ $89,000 (tag: GBOT_BUY_123, keeping only $89,500)
✅ [SAGA] Successfully canceled order #12345 @ $89,000
📊 [SAGA] Cancellation summary: 1 succeeded, 0 failed out of 1 total
[SAGA] Verifying no duplicate order exists...
✅ [SAGA] No duplicate found, placing new BUY @ $89,500
✅ BUY order placed @ $89,500 (Order: XYZ789)
```

### Step 3: Verify Log Indicators

✅ **GOOD SIGNS:**
- `✅ Successfully canceled` - Cancellations working
- `📊 Cancellation summary: X succeeded, 0 failed` - All cancellations succeeded
- `No duplicate found` - Exchange verification working
- Only ONE new order placed

❌ **BAD SIGNS:**
- `❌ Failed to cancel order` - Cancellation failed
- `❌ Timeout cancelling order` - API timeout
- `Cancellation summary: X succeeded, Y failed` (Y > 0) - Some cancellations failed
- `⚠️ Order already exists - skipping placement` - Duplicate detected (this is actually OK - it means the safety check is working!)

---

## Test Method 2: Exchange Verification (Most Reliable)

### Step 1: Get Current State

```bash
# Using curl (replace with your API key)
curl -X GET "https://api.india.delta.exchange/v2/orders" \
  -H "api-key: YOUR_API_KEY" \
  | jq '.result[] | select(.state == "open" and .reduce_only == false)'
```

### Step 2: Count Pending Entry Orders

**LONG Mode - Check BUY Orders:**
```bash
# Count non-TP BUY orders (reduce_only=false)
curl -X GET "https://api.india.delta.exchange/v2/orders" \
  -H "api-key: YOUR_API_KEY" \
  | jq '[.result[] | select(.state == "open" and .side == "buy" and .reduce_only == false)] | length'

# Expected result: 1 (only ONE pending BUY order)
```

**SHORT Mode - Check SELL Orders:**
```bash
# Count non-TP SELL orders (reduce_only=false)
curl -X GET "https://api.india.delta.exchange/v2/orders" \
  -H "api-key: YOUR_API_KEY" \
  | jq '[.result[] | select(.state == "open" and .side == "sell" and .reduce_only == false)] | length'

# Expected result: 1 (only ONE pending SELL order)
```

### Step 3: After Each TP Fill

**Immediately check orders again:**
```bash
# Wait 5 seconds for saga to complete
sleep 5

# Then check again
curl -X GET "https://api.india.delta.exchange/v2/orders" \
  -H "api-key: YOUR_API_KEY" \
  | jq '[.result[] | select(.state == "open" and .side == "buy" and .reduce_only == false)]'
```

**Expected:**
- Only ONE entry order
- Price should be (last_tp_price - step) for LONG
- Price should be (last_tp_price + step) for SHORT

---

## Test Method 3: WebUI Monitoring (Visual)

### Step 1: Open WebUI

```bash
# Open in browser
open http://localhost:5555
```

### Step 2: Navigate to Orders Tab

- Click on "Orders" or "Open Orders"
- Filter by "Entry Orders" (non-reduce_only)

### Step 3: Watch During TP Fill

**Before TP Fill:**
- Note the current pending entry order price

**After TP Fill:**
- Wait 5-10 seconds
- Refresh orders list
- **Expected:** Different entry order price (moved to TP - step)
- **Expected:** Only ONE entry order visible

---

## Test Scenarios

### Scenario 1: Single TP Fill ✅

**Setup:**
- LONG mode with positions at $89k, $90k, $91k
- Pending BUY at $88k

**Trigger:**
- Market rises to $90k, TP fills

**Expected Result:**
1. Old BUY at $88k is canceled
2. New BUY placed at $89k (TP - step)
3. Only ONE pending BUY remains

**How to Verify:**
```bash
# Check logs
pm2 logs gridbot-live | grep "Cancellation summary"

# Check exchange
curl ... | jq '[.result[] | select(.side == "buy" and .reduce_only == false)] | length'
# Should return: 1
```

---

### Scenario 2: Rapid Multiple TPs ⚡

**Setup:**
- LONG mode with many positions
- Market rising rapidly

**Trigger:**
- Multiple TPs fill within seconds

**Expected Result:**
- Each saga runs independently
- Duplicate checks prevent double placement
- Final state: ONE pending order at correct level

**How to Verify:**
```bash
# Watch logs in real-time
pm2 logs gridbot-live --lines 200

# Look for:
# - Multiple saga executions
# - "duplicate_order_on_exchange" skips (OK if this happens)
# - Final cancellation summary shows all succeeded
```

---

### Scenario 3: Cancellation Timeout ⏱️

**Setup:**
- Simulate by using slow network or high API load

**Trigger:**
- TP fills during network congestion

**Expected Result:**
- Cancellation times out after 5 seconds
- Error logged with ❌
- Duplicate check catches existing order
- New order skipped to prevent duplicate

**How to Verify:**
```bash
# Check logs for timeout
pm2 logs gridbot-live | grep "Timeout cancelling"

# Check if duplicate prevention worked
pm2 logs gridbot-live | grep "Order already exists"
```

---

## Success Criteria

### ✅ PASS if:
1. After each TP fill, only ONE pending entry order exists
2. Logs show `✅ Successfully canceled` for old orders
3. Cancellation summary shows "0 failed"
4. New order price is correct (TP ± step)
5. No duplicate orders on exchange

### ❌ FAIL if:
1. Multiple entry orders exist after TP fill
2. Logs show `❌ Failed to cancel` without duplicate skip
3. Old order remains on exchange
4. New order not placed (and no "duplicate" skip logged)

---

## Troubleshooting

### Issue: Multiple Entry Orders After TP

**Diagnosis:**
```bash
# Check how many entry orders
curl ... | jq '.result[] | select(.side == "buy" and .reduce_only == false) | .id'

# Check bot logs
pm2 logs gridbot-live | grep -A 10 "Cancellation summary"
```

**Possible Causes:**
1. Cancellation failed (check logs for ❌)
2. API timeout (check logs for "Timeout cancelling")
3. Manual orders placed (check client_order_id doesn't start with GBOT_)

**Fix:**
- If manual orders: They will be preserved (working as designed)
- If bot orders: Check why cancellations failed
- Emergency: Manually cancel extra orders

---

### Issue: No New Order Placed

**Diagnosis:**
```bash
pm2 logs gridbot-live | grep "Order already exists"
```

**Possible Causes:**
1. Duplicate detected (working as designed - check logs)
2. Order placement failed (check logs for errors)
3. Out of grid bounds (check logs for "out of bounds")

---

## Monitoring Commands

### Quick Health Check
```bash
# Check bot status
pm2 list | grep gridbot

# Check recent errors
pm2 logs gridbot-live --err --lines 50

# Check cancellation stats
pm2 logs gridbot-live | grep "Cancellation summary" | tail -10
```

### Detailed Analysis
```bash
# Count successful cancellations today
pm2 logs gridbot-live --lines 10000 | grep "Successfully canceled" | wc -l

# Count failed cancellations today
pm2 logs gridbot-live --lines 10000 | grep "Failed to cancel" | wc -l

# Find duplicate prevention triggers
pm2 logs gridbot-live --lines 10000 | grep "Order already exists"
```

---

## Report Template

After testing, fill this out:

```
Test Date: __________
Bot Mode: LONG / SHORT
Test Duration: __________ minutes

TP Fills Observed: __________
Successful Cancellations: __________
Failed Cancellations: __________
Duplicate Skips: __________

Final Verdict: PASS / FAIL

Notes:
- 
- 
- 

Logs Attached: YES / NO
```

---

## Emergency Rollback

If the fix causes issues:

```bash
# Stop bot
pm2 stop gridbot-live

# Revert to previous version
cd /Users/ssr/Projects/WorkingBot
git log --oneline -10  # Find commit before Dec 11
git checkout COMMIT_HASH bot/strategy/sagas/fill_processing_saga.py

# Restart bot
pm2 restart gridbot-live

# Verify rollback
pm2 logs gridbot-live
```

---

## Contact Info

If you encounter issues or need clarification:
- Check logs first: `pm2 logs gridbot-live`
- Review fix documentation: `SINGLE_PENDING_ORDER_FIX_DEC11_2025.md`
- Check strategy: `strategy.md`

---

**Last Updated:** December 11, 2025  
**Next Review:** After 24 hours of live trading
