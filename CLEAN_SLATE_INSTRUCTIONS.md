# Clean Slate Instructions - November 19, 2025

## What This Does

Completely clears the bot's in-memory state and gives it a fresh start. This will:

✅ Clear all Python bytecode cache (`__pycache__`, `.pyc` files)
✅ Remove any state persistence files (if they exist)
✅ Force bot to start with empty PositionActor and OrderActor state
✅ Bot will fetch all positions/orders fresh from exchange on startup

❌ Does NOT delete:
- Configuration files (`config.yaml`)
- Log files
- SQL database events
- Exchange orders/positions (those stay on exchange)

---

## Step-by-Step Process

### Step 1: Clear Python Cache (DONE ✅)
```bash
python3 scripts/clear_bot_state.py
```

**Result**: Cleared 17 `__pycache__` directories

### Step 2: Verify Bot is Running
```bash
pm2 status
```

You should see:
```
│ gridbot-live  │ online  │
```

### Step 3: Restart Bot with Clean State
```bash
pm2 restart gridbot-live
```

### Step 4: Monitor Startup
```bash
pm2 logs gridbot-live --lines 100
```

---

## What to Expect on Startup

### 1. Actor Initialization (0-5 seconds)
```
🎭 [PositionManager] Actor started
🎭 [OrderManager] Actor started
```

**State will be EMPTY**:
- `open_tranches: []`
- `pending_buy: None`
- `pending_sell: None`

### 2. State Validation (5-10 seconds)
```
🚨 Found 5 positions with None IDs - REMOVING THEM
   Removing broken position: {...}
✅ State validation complete: 0 positions kept, 5 removed
```

**This removes any corrupted positions from previous sessions.**

### 3. Exchange Sync (10-20 seconds)
The bot will fetch current state from exchange:
- Open positions
- Open orders
- Current price

### 4. Opportunistic Recovery Check (20-30 seconds)
```
Checking for startup opportunistic recovery...
```

If recovery is needed, it will execute. Otherwise:
```
No recovery needed - price within normal range
```

### 5. Normal Trading Starts (30+ seconds)
```
[HB] Positions: 0/5 | Price: $[price] | ✅ ACTIVE
```

---

## Verification Checklist

After restart, verify these in logs:

### ✅ Clean State Indicators
- [ ] "Actor started" messages for PositionManager and OrderManager
- [ ] "State validation complete: 0 positions kept, X removed"
- [ ] No "EMERGENCY TP" messages for None positions
- [ ] "All positions have TP protection" (in first reconciliation)

### ✅ Normal Operation
- [ ] Heartbeat messages showing current positions
- [ ] Grid orders being placed normally
- [ ] No error messages about None IDs

### 🚨 Warning Signs (Should NOT see these)
- [ ] "REJECTED position with invalid ID: None"
- [ ] "EMERGENCY TP] Placing TP for position None"
- [ ] "Found X unprotected positions" (repeatedly)

---

## Monitoring Commands

### Real-time logs
```bash
pm2 logs gridbot-live
```

### Check for None position errors
```bash
pm2 logs gridbot-live --lines 200 --nostream | grep -i "none"
```

### Check state validation
```bash
pm2 logs gridbot-live --lines 200 --nostream | grep "State validation"
```

### Check reconciliation
```bash
pm2 logs gridbot-live --lines 200 --nostream | grep "RECONCILIATION"
```

### Check current positions
```bash
pm2 logs gridbot-live --lines 50 --nostream | grep "Positions:"
```

---

## If Problems Persist

If you still see issues after clean slate restart:

### 1. Check if state validation ran
```bash
pm2 logs gridbot-live --lines 500 --nostream | grep "State validation"
```

Should see: "State validation complete: 0 positions kept, X removed"

### 2. Check for lingering None positions
```bash
pm2 logs gridbot-live --lines 500 --nostream | grep "position None"
```

Should see: NO results (or only SKIPPING messages)

### 3. Force another restart
```bash
pm2 restart gridbot-live
```

### 4. Check exchange state
The bot syncs with exchange on startup. If exchange has corrupted orders:
```bash
# Check via WebUI or exchange directly
```

---

## Technical Details

### Actor State Reset
The bot uses an Actor model with in-memory state:

**PositionActor State**:
```python
{
    "open_tranches": [],      # Empty on clean start
    "pending_buy": None,
    "pending_sell": None,
    "total_positions_opened": 0,
    "total_positions_closed": 0
}
```

**OrderActor State**:
```python
{
    "active_orders": {},      # Empty on clean start
    "order_history": []
}
```

### State Validation
On startup, `validate_state()` runs and:
1. Checks all positions for valid IDs
2. Removes any with `None` or invalid IDs
3. Clears any stale pending orders
4. Rebuilds position index

### Exchange Sync
After state validation, bot fetches from exchange:
1. Current open positions
2. Current open orders
3. Reconciles with internal state

---

## Success Criteria

After 10 minutes of running:

✅ **No errors** about None positions
✅ **No emergency TP spam** (max 1 reconciliation cycle)
✅ **Normal grid trading** active
✅ **Positions tracked correctly** with proper IDs
✅ **Reconciliation clean** ("All positions have TP protection")

---

## Clean Slate Status

✅ **Python cache cleared**: 17 directories removed
✅ **State files cleared**: None found (already clean)
✅ **Code fixes applied**: All validation and cleanup logic in place
✅ **Ready for restart**: Bot will start with completely clean state

**Next step**: Restart the bot whenever you're ready!

```bash
pm2 restart gridbot-live
```
