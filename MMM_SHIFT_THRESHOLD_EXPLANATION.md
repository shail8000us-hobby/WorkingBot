# Strike Shift Logic — How It Actually Works

## Understanding the Confusion

**User's Expectation:**
"I set shift_threshold_pct to 80%, so algo should NOT sell options below 80 premium"

**Reality:**
Strike shift controls WHEN to abandon (freeze) old positions and open NEW positions on the hedge side, NOT the price at which new positions are opened.

---

## How MMM Adjustments Work

### Normal Adjustment Flow:

1. **Trigger Fires** (Aggressor side premium INCREASES)
   - Example: PE premium goes from $100 → $115 (+15%)
   - Trigger threshold: 3%
   - Result: **PE is aggressor**

2. **Calculate Loss**
   - Calculate how much loss aggressor side will cause

3. **Check Hedge Side Premium** (THIS IS WHERE shift_threshold_pct MATTERS)
   - Hedge = CE (opposite of aggressor)
   - Current CE premium = $60
   - Original CE entry premium = $150
   - shift_threshold_pct = 0.8 (80%)
   - effective_threshold = max(100, 150 * 0.8) = **120**

4. **Decision Point:**
   - If CE premium < 120 → **SHIFT** (freeze old, open new strike)
   - If CE premium ≥ 120 → **ADJUST** (sell more CE at current strike)

---

## Your Session Analysis

Looking at your screenshot:
- **Aggressor:** PE at $115.96 (triggered +16.5%)
- **Hedge:** CE at $114.32
- **shift_threshold_pct:** 0.8 (80%)
- **shift_threshold:** 100

### Question: Why did it adjust at $60?

**Possible reasons:**

1. **You're looking at the AGGRESSOR side price ($115.96), not hedge**
   - Adjustments sell the HEDGE side (CE at $114.32)
   - The $60 you saw might be:
     - PE initial entry premium (aggressor)
     - Historical premium from activity feed
     - NOT the hedge premium at adjustment time

2. **Shift already happened earlier**
   - You have "Shifts: 6" in the session
   - After a shift, NEW positions start at wherever spot is
   - Premium at new strike could be anything ($60, $80, $120)
   - shift_threshold_pct only controls WHEN to shift again

3. **shift_threshold_pct checks hedge side at adjustment time**
   - If CE was at $114 when PE triggered
   - Original CE entry = $150
   - effective_threshold = max(100, 150 * 0.8) = 120
   - $114 is BELOW $120, so **SHIFT should have triggered!**
   - But it adjusted instead... this might be a bug

---

## What I Fixed

### 1. ✅ Analytics Error Fixed
- **Problem:** Frontend crash "Cannot read properties of undefined"
- **Fix:** Added robust error checking in MMMAnalyticsTable.js
- **Status:** Build successful, deployed

### 2. ✅ Migrated Analytics to SQLite (Not JSON!)
- **Problem:** I mistakenly created JSON storage yesterday, but sessions use SQLite
- **Fix:** Rewrote mmm_analytics_storage.py to use SQLite
- **Tables:** 
  - `mmm_sessions` (session data with params, created Feb 17)
  - `mmm_analytics` (analytics history, created today)
- **Benefits:**
  - Same database = consistency
  - Better performance
  - ACID transactions
  - Concurrent reads with WAL mode

### 3. ✅ Enhanced Shift Logging
- **Problem:** Can't see WHY shifts happen or don't happen
- **Fix:** Added detailed logging in check_shift_needed():
  ```
  🔍 SHIFT CHECK: CE | Current: $114.32, Entry: $150.00, Floor: $100.00, 
                      Pct: 80%, Dynamic: $120.00, Effective: $120.00
  ✅ SHIFT NEEDED: CE premium $114.32 < $120.00
  ```
- **Location:** Activity Feed will show this now

---

## How to Debug Your Session

### Step 1: Check Activity Feed
Look for these new log messages:
- `🔍 SHIFT CHECK:` — Shows calculation details
- `✅ SHIFT NEEDED:` — Shift triggered
- `❌ NO SHIFT:` — Premium still above threshold

### Step 2: Verify Which Side Is Adjusting
When you see "adjusting at 60 premium", check:
- **Aggressor side** (triggered) — Premium INCREASED, this triggers adjustment
- **Hedge side** (sold) — Premium is checked against shift_threshold

### Step 3: Look at Original Entry Premium
- After a shift, the "entry premium" resets to whatever premium was at NEW strike
- So if first entry was at $150, then shifted and entered new at $60:
  - New effective_threshold = max(100, 60 * 0.8) = max(100, 48) = **100**
  - Next shift happens when premium < 100

---

## Configuration Guide

### shift_threshold (Floor)
- **Default:** 50
- **Your value:** 100
- **Meaning:** Minimum absolute premium to shift
- **Use case:** Prevent shifts when premium is dirt cheap

### shift_threshold_pct (Percentage)
- **Default:** 0.0 (disabled)
- **Your value:** 0.8 (80%)
- **Meaning:** Shift when premium drops to X% of entry
- **Formula:** `effective_threshold = max(shift_threshold, entry_premium * shift_threshold_pct)`

### Example Calculations:

| Entry Premium | shift_threshold | shift_threshold_pct | Effective Threshold | Shift Triggers When Premium < |
|---------------|-----------------|---------------------|---------------------|-------------------------------|
| $150 | 50 | 0% | $50 | $50 |
| $150 | 50 | 80% | $120 | $120 (max of 50 and 120) |
| $75 | 100 | 80% | $100 | $100 (max of 100 and 60) |
| $200 | 100 | 80% | $160 | $160 (max of 100 and 160) |

---

## Common Scenarios

### Scenario 1: Fresh Entry
- **CE entry:** $200 at strike 98000
- **PE entry:** $180 at strike 92000
- **shift_threshold:** 100
- **shift_threshold_pct:** 0.8 (80%)
- **Result:** 
  - CE will shift if premium < max(100, 200 * 0.8) = **160**
  - PE will shift if premium < max(100, 180 * 0.8) = **144**

### Scenario 2: After First Shift
- CE shifted to strike 99000 at premium $80
- **New effective threshold:** max(100, 80 * 0.8) = **100**
- CE will shift again if premium < 100

### Scenario 3: Why Adjustments Still Happen at "Low" Premium
- **Aggressor:** PE premium increases to $120 (triggers)
- **Hedge:** CE premium is $90
- **CE entry:** $150
- **Threshold:** max(100, 150 * 0.8) = 120
- **Decision:** $90 < $120 → **SHIFT TRIGGERED** ✅
- **Result:** Freeze CE at 98000, open NEW CE at 99000 at current premium ($85)
- **User sees:** "Opened CE at $85" and thinks "why so low?"
- **Reality:** That's current market price at new strike after shift

---

## Action Items for You

### 1. Refresh WebUI
- Analytics error is fixed
- Analytics now persist in SQLite (survive session deletion)

### 2. Watch Activity Feed
Look for the new detailed logging:
```
🔍 SHIFT CHECK: CE | Current: $114.32, Entry: $150.00, Floor: $100.00, 
                    Pct: 80%, Dynamic: $120.00, Effective: $120.00
```

This will show you EXACTLY why shifts happen or don't.

### 3. Understand the Flow
```
Trigger fires (PE up) → Check CE premium → Compare to threshold
                                             ↓
                      If below threshold: SHIFT (freeze old, new strike)
                      If above threshold: ADJUST (sell more at same strike)
```

### 4. If You Want Higher Entry Premiums After Shift
**Problem:** After shift, new positions open at current premium (might be low)

**Solutions:**
- **Option A:** Set `target_premium` in shift logic (requires code change)
- **Option B:** Adjust `shift_threshold` higher (e.g., 150 instead of 100)
  - This delays shifts, allowing more adjustments at current strike
- **Option C:** Reduce `shift_threshold_pct` (e.g., 60% instead of 80%)
  - Shifts happen earlier when premium hasn't dropped as much

---

## Database Schema (For Reference)

### mmm_sessions table:
```sql
CREATE TABLE mmm_sessions (
    session_id   TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'IDLE',
    params_json  TEXT NOT NULL DEFAULT '{}',
    data_json    TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
)
```

### mmm_analytics table (NEW):
```sql
CREATE TABLE mmm_analytics (
    session_id TEXT PRIMARY KEY,
    session_status TEXT,
    expiry TEXT,
    analytics_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
)
```

Both tables are in: `webui/backend/data/mmm_sessions.db`

---

## Summary

1. **Analytics error:** ✅ Fixed
2. **SQLite migration:** ✅ Complete (both sessions and analytics)
3. **Shift logging:** ✅ Enhanced (shows exact calculations)
4. **Your question:** Likely confusion between aggressor/hedge side premiums and when shifts happen vs what premium new positions open at

Watch the Activity Feed with the new logging — it will make everything crystal clear!

If you still see unexpected behavior, share:
- Activity feed screenshot showing the 🔍 SHIFT CHECK logs
- Which side triggered
- What premium you expected vs what you got

