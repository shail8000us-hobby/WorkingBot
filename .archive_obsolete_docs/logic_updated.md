# GridBot Trading Logic - UPDATED (Nov 20, 2025)

**Status:** ✅ VERIFIED AGAINST ACTUAL CODE  
**Bot Version:** v5.0 (Standalone Engines + Unified API)  
**Config:** Ref: $100k, Lower: $96k, Upper: $110k, Step: $1k

---

## ⚠️ CRITICAL CHANGES

**This replaces the OLD logic.md which is OUTDATED.**

**Major Changes:**
1. Recovery is now STANDALONE (recovery_runner.py)
2. Reconciliation is now STANDALONE (reconciliation_runner.py)  
3. New UnifiedAPIClient for all systems
4. Bot reduced 17.6% (3,530 lines)

---

## 📁 FILE STRUCTURE

### Main Bot: `async_gridbot.py` (3,530 lines)
- Lines 215-225: UnifiedAPIClient init
- Lines 1050-1060: Async tasks
- Lines 2703-2850: Reconciliation action processor

### Recovery: `recovery_runner.py` (320 lines)
- Runs BEFORE bot (separate process)
- Detects missed grids (MAX 3)
- Writes recovery_state.json

### Reconciliation: `reconciliation_runner.py` (~650 lines)
- Runs ALONGSIDE bot (separate process)
- **EVENT-DRIVEN + SCHEDULED**
- Detects 4 types of discrepancies
- Handles shutdown cleanup (<1 second)
- Writes action_queue.json
- Monitors signal files for immediate triggers

### API Layer: `unified_api_client.py` (468 lines)
- WebSocket (optional) + REST (always)
- Automatic fallback
- Circuit breaker + rate limiter

---

## 🔄 ORDER FLOW EXAMPLES

### Example 1: LONG Entry Fill

**Initial:** Pending BUY @ $99k

**Fill:** BUY fills @ $99k

**Saga Steps:**
1. Add position (entry $99k)
2. Place TP @ $100k
3. Update TP order ID
4. Clear pending state
5. **SINGLE PENDING ORDER RULE:**
   - Get all open orders
   - Cancel ALL pending BUYs (except next price)
6. Place next BUY @ $98k

**Result:** ONE pending BUY @ $98k, ONE TP @ $100k

---

### Example 2: Recovery (Standalone)

**Scenario:** Bot down, price $100k → $96.5k

**Process:**
```bash
# 1. Run recovery BEFORE bot
python3 -m bot.strategy.recovery.recovery_runner

# 2. Recovery detects missed grids: $99k, $98k, $97k
# 3. Places 3 MARKET orders @ $96.5k
# 4. Places TPs @ $100k, $99k, $98k
# 5. Writes recovery_state.json
# 6. Exits

# 7. Start bot
python3 -m bot.strategy.async_gridbot

# 8. Bot reads recovery_state.json
# 9. Skips recovered grids
```

**Result:** 3 positions, $7.5k capital saved

---

### Example 3: Reconciliation (Missed Fill)

**Scenario:** WebSocket missed fill

**Process:**
```
Reconciliation Engine (every 5 min):
1. Load bot_state.json
2. Query exchange
3. Detect: Order #555 is FILLED (bot thinks PENDING)
4. Generate action: process_missed_fill
5. Write action_queue.json

Bot Action Processor (every 10 sec):
1. Read action_queue.json
2. Execute: process_missed_fill
3. Create saga for fill
4. Mark action completed
```

**Result:** Missed fill recovered, state synced

---

## ⚠️ POTENTIAL CONFLICTS

### 1. Recovery vs Normal Trading
**Status:** ✅ RESOLVED
- Recovery runs BEFORE bot
- Bot reads recovery_state.json
- Skips recovered grids

### 2. Reconciliation vs WebSocket
**Status:** ✅ RESOLVED  
- Deduplication at detection level
- Checks if position exists

### 3. Single Pending Order Rule
**Status:** ✅ VERIFIED
- Cancels ALL other pending orders
- Only ONE pending entry order

### 4. Circuit Breaker
**Status:** ⚠️ NEEDS MONITORING
- Opens after 5 failures
- Blocks requests for 60s
- Need alerting

### 5. Price Staleness
**Status:** ✅ RESOLVED
- Bot calls update_price_from_websocket()
- Automatic REST fallback

---

## 📊 VERIFICATION STATUS

**Code Verified:**
- ✅ Recovery is standalone
- ✅ Reconciliation is standalone
- ✅ UnifiedAPIClient exists
- ✅ Single pending order rule implemented
- ✅ Bot is 3,530 lines

**Testing Verified:**
- ✅ Bot compiles and runs
- ✅ WebSocket connects
- ✅ Orders placed successfully
- ✅ All systems operational

**Documentation:**
- ✅ AI_CONTEXT.md updated
- ✅ New architecture docs created
- ❌ OLD logic.md is outdated

---

**See CURRENT_ARCHITECTURE_NOV20.md for complete details**
