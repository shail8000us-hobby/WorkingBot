# Phase 0: Emergency Tactical Fixes - Deployment Guide

**Date**: November 9, 2025  
**Target**: Production GridBot v2.0  
**Risk Level**: LOW (minimal code changes, well-tested patterns)  
**Estimated Downtime**: < 5 minutes

---

## Pre-Deployment Checklist

### ✅ Verify Changes Are In Place
```bash
cd /Users/ssr/Projects/WorkingBot

# Check backups exist
ls -lh bot/strategy/modules/fill_detector.py.backup_nov9_phase0
ls -lh bot/strategy/gridbot.py.backup_nov9_phase0
ls -lh bot/strategy/modules/position_manager.py.backup_nov9_phase0

# Verify syntax (should see 3 "OK" messages)
python3 -m py_compile bot/strategy/modules/fill_detector.py && echo "✅ fill_detector.py: OK"
python3 -m py_compile bot/strategy/gridbot.py && echo "✅ gridbot.py: OK"
python3 -m py_compile bot/strategy/modules/position_manager.py && echo "✅ position_manager.py: OK"
```

### ✅ Check Current System Status
```bash
# Check if bot is running
ps aux | grep "python.*run_bot.py"

# Check recent logs for any errors
tail -50 bot_live.log | grep -i "error\|critical"

# Check current positions
cat runtime_state.json | jq '.data.open_tranches | length'

# Check pending orders
cat runtime_state.json | jq '.data.pending_buy'
```

### ✅ Prepare Rollback Plan
```bash
# Create timestamped backup of current state
cp runtime_state.json runtime_state.json.pre_phase0_$(date +%Y%m%d_%H%M%S)

# Verify rollback files exist
ls -lh bot/strategy/modules/*.backup_nov9_phase0
```

---

## Deployment Steps

### Step 1: Schedule Deployment Window

**Recommended Time**: 2-4 AM UTC (low trading volume)

```bash
# Check current UTC time
date -u

# Check market volatility (should be low)
curl -s "https://api.delta.exchange/v2/tickers/BTCUSD" | jq '.result.stats.volume24h'
```

### Step 2: Graceful Bot Shutdown

```bash
# Send SIGTERM for graceful shutdown (preserves TP orders)
pkill -SIGTERM -f "python.*run_bot.py"

# Monitor shutdown (should see "GRACEFUL SHUTDOWN" in logs)
tail -f bot_live.log
```

**Expected Log Output**:
```
🧹 GRACEFUL SHUTDOWN
📊 LONG MODE CLEANUP:
  ✅ Cancel pending BUY orders (prevent new positions)
  ✅ Preserve TP SELL orders (protect LONG positions)
🎯 Found pending BUY @ $65,000 (ID: 12345678)
✅ BUY order cancelled successfully
✅ PRESERVED 3 TP SELL ORDERS (Protecting LONG Positions):
   1. TP @ $66,000 (entry: $65,000, +1.54%) - Order ID: 87654321
   2. TP @ $67,000 (entry: $66,000, +1.52%) - Order ID: 87654322
   3. TP @ $68,000 (entry: $67,000, +1.49%) - Order ID: 87654323
✅ Final state persisted
✅ GridBot stopped
```

**Wait for**: "GridBot stopped" message (typically 5-15 seconds)

### Step 3: Verify Clean Shutdown

```bash
# Confirm process stopped
ps aux | grep "python.*run_bot.py"
# Should return nothing (or only grep itself)

# Check final state was saved
ls -lh runtime_state.json
stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" runtime_state.json
# Should show timestamp within last minute

# Verify state integrity
python3 -c "
import json
with open('runtime_state.json', 'r') as f:
    state = json.load(f)
print(f\"✅ State file valid\")
print(f\"   Open positions: {len(state['data']['open_tranches'])}\")
print(f\"   Checksum: {state.get('checksum', 'N/A')}\")
"
```

### Step 4: Backup Current Production Code

```bash
# Create deployment timestamp
DEPLOY_TIME=$(date +%Y%m%d_%H%M%S)

# Backup entire bot directory (optional but recommended)
tar -czf ../WorkingBot_backup_pre_phase0_${DEPLOY_TIME}.tar.gz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='bot_live.log*' \
    .

echo "✅ Full backup created: WorkingBot_backup_pre_phase0_${DEPLOY_TIME}.tar.gz"
```

### Step 5: Deploy Phase 0 Changes

**Phase 0 changes are already in place** (implemented earlier), so no file copying needed.

Verify changes:
```bash
# Check Fill Queue Size (should be 1000)
grep -n "queue_size: int = 1000" bot/strategy/modules/fill_detector.py
# Should show: queue_size: int = 1000  # ✅ PHASE 0 FIX

# Check Lock Logging (should exist)
grep -n "PHASE 0 FIX.*LOCK" bot/strategy/gridbot.py | head -5
# Should show lock acquisition/release logging

# Check Force Persistence (should have force parameter)
grep -n "def persist_runtime_state.*force:" bot/strategy/modules/position_manager.py
# Should show: def persist_runtime_state(self, filename: str = 'runtime_state.json', force: bool = False)

# Check Unknown Order ID Handling (should be CRITICAL)
grep -n "PHASE 0 FIX.*CRITICAL" bot/strategy/gridbot.py
# Should show critical logging + reconciliation trigger
```

### Step 6: Start Bot with Phase 0 Enhancements

```bash
# Start bot in background
nohup python3 run_bot.py > bot_startup.log 2>&1 &

# Get process ID
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

# Save PID for monitoring
echo $BOT_PID > bot.pid
```

### Step 7: Monitor Startup (Critical!)

```bash
# Watch startup logs in real-time
tail -f bot_live.log
```

**Expected Startup Sequence**:
```
🚀 GRIDBOT - REFACTORED ARCHITECTURE
🎯 Grid Mode: LONG
✅ GridCalculator initialized
✅ PositionManager initialized (max_open=5)
✅ FillDetector initialized (queue_size=1000, dedup_size=5000)  # ← NEW: 1000!
✅ OrderManager initialized
✅ Reconciliation initialized
✅ All monitoring systems initialized (5 layers + WebUI writer)
✅ Fill processor started - sequential processing active

🔄 CRASH RECOVERY: Loading persisted state...
✅ State recovered successfully!
   📊 Recovered Positions: 3
   📝 Recovered Pending Buy: No
   🏷️  Session Tag: GBOT_1699564800
   📍 Recovered position details:
      - pos_1: 1 @ 65000 (TP: 66000)
      - pos_2: 1 @ 66000 (TP: 67000)
      - pos_3: 1 @ 67000 (TP: 68000)

🔄 Reconciling orphaned orders from exchange...
✅ No orphaned bot BUY orders found on exchange
⏳ Waiting for initial price...
✅ Got price: $68,500

📍 Placing initial MAKER BUY @ $64,000
   Current Market: $68,500
✅ Initial MAKER BUY placed @ $64,000 (Volatility: SAFE)
```

**Key Indicators of Successful Deployment**:
- ✅ `FillDetector initialized (queue_size=1000, ...)` - Queue size increased
- ✅ `State recovered successfully!` - Crash recovery working
- ✅ `Recovered Positions: X` - Positions loaded from disk
- ✅ `No orphaned bot BUY orders found` - Exchange sync clean
- ✅ `Initial MAKER BUY placed` - Bot active and trading

**Warning Signs** (if seen, proceed to rollback):
- ❌ `Failed to load runtime state` - State corruption
- ❌ `Error during orphaned order reconciliation` - Exchange sync failed
- ❌ Any Python exceptions during initialization

### Step 8: Verify Phase 0 Enhancements

**Test 1: Verify Larger Fill Queue**
```bash
# Check queue stats in logs (should show max depth and total queued)
tail -100 bot_live.log | grep "Fill queue depth"
# Example: Fill queue depth: 5 (high load) - Should never reach 1000 in normal operation
```

**Test 2: Verify Lock Logging (if DEBUG enabled)**
```bash
# Enable debug logging temporarily to see lock messages
# In .env file: LOG_LEVEL=DEBUG
# Then check logs:
tail -100 bot_live.log | grep "\[LOCK\]"
# Should see: 🔒 [LOCK] Attempting to acquire state_lock
#             🔒 [LOCK] Acquired state_lock
#             🔓 [LOCK] Releasing state_lock
```

**Test 3: Verify Immediate Persistence**
```bash
# Watch for position additions (should see immediate persistence)
tail -100 bot_live.log | grep "Position added + persisted"
# Example: ✅ Position added + persisted: 65000
```

**Test 4: Verify Unknown Order ID Handling (Manual Test)**
```bash
# Place a manual order outside the bot (via Delta Exchange UI)
# Wait for fill
# Check logs for CRITICAL alert + reconciliation
tail -100 bot_live.log | grep "FILL FOR UNKNOWN ORDER ID"
# Should see: 🚨 FILL FOR UNKNOWN ORDER ID - TRIGGERING RECONCILIATION
#             🔄 Triggering full reconciliation to sync with exchange...
#             ✅ Reconciliation completed
```

---

## Post-Deployment Monitoring (First 24 Hours)

### Metrics to Watch

**1. Fill Queue Depth** (should never reach 1000)
```bash
# Check every 5 minutes
watch -n 300 'tail -100 bot_live.log | grep "Fill queue depth" | tail -1'
```

**2. State Persistence** (should happen immediately after fills)
```bash
# Monitor persistence frequency
watch -n 60 'ls -lh runtime_state.json'
```

**3. Lock Contention** (if DEBUG logging enabled)
```bash
# Check for long lock hold times
tail -1000 bot_live.log | grep "LOCK" | grep -v "Acquired" | grep -v "Releasing"
# Should be minimal
```

**4. Unknown Order IDs** (should be rare)
```bash
# Alert on unknown orders
tail -1000 bot_live.log | grep "UNKNOWN ORDER ID" | wc -l
# Should be 0 in normal operation
```

### Automated Monitoring Script

Create `monitor_phase0.sh`:
```bash
#!/bin/bash
# Phase 0 Post-Deployment Monitor

LOG_FILE="bot_live.log"
ALERT_EMAIL="your-email@example.com"  # Optional

echo "=== Phase 0 Post-Deployment Monitor ==="
echo "Started: $(date)"
echo ""

# Check 1: Queue depth
MAX_QUEUE=$(tail -1000 $LOG_FILE | grep -o "Fill queue depth: [0-9]*" | \
            sed 's/Fill queue depth: //' | sort -rn | head -1)
echo "✓ Max queue depth (last 1000 lines): ${MAX_QUEUE:-0}/1000"

if [ "$MAX_QUEUE" -gt 800 ]; then
    echo "⚠️  WARNING: Queue approaching capacity!"
fi

# Check 2: Persistence rate
PERSIST_COUNT=$(tail -1000 $LOG_FILE | grep "State persisted" | wc -l)
echo "✓ State persistence events: $PERSIST_COUNT"

# Check 3: Unknown orders
UNKNOWN_COUNT=$(tail -1000 $LOG_FILE | grep "UNKNOWN ORDER ID" | wc -l)
echo "✓ Unknown order IDs: $UNKNOWN_COUNT"

if [ "$UNKNOWN_COUNT" -gt 0 ]; then
    echo "⚠️  WARNING: Unknown orders detected - check reconciliation"
fi

# Check 4: Errors
ERROR_COUNT=$(tail -1000 $LOG_FILE | grep -i "error\|critical" | grep -v "CRITICAL CHECK" | wc -l)
echo "✓ Error/Critical logs: $ERROR_COUNT"

if [ "$ERROR_COUNT" -gt 10 ]; then
    echo "⚠️  WARNING: High error rate!"
fi

echo ""
echo "Monitor complete: $(date)"
```

Run every hour:
```bash
chmod +x monitor_phase0.sh
watch -n 3600 './monitor_phase0.sh'
```

---

## Rollback Procedure (If Needed)

### When to Rollback
- ❌ Bot crashes repeatedly (>3 crashes in 1 hour)
- ❌ Fill queue overflows despite increased size
- ❌ State corruption detected
- ❌ Unknown order ID flood (>10 in 1 hour)
- ❌ Performance degradation (fills taking >60s to process)

### Rollback Steps

```bash
# 1. Stop bot immediately
pkill -SIGTERM -f "python.*run_bot.py"
sleep 5
pkill -9 -f "python.*run_bot.py"  # Force kill if needed

# 2. Restore original code from backups
cp bot/strategy/modules/fill_detector.py.backup_nov9_phase0 bot/strategy/modules/fill_detector.py
cp bot/strategy/gridbot.py.backup_nov9_phase0 bot/strategy/gridbot.py
cp bot/strategy/modules/position_manager.py.backup_nov9_phase0 bot/strategy/modules/position_manager.py

# 3. Verify syntax
python3 -m py_compile bot/strategy/modules/fill_detector.py
python3 -m py_compile bot/strategy/gridbot.py
python3 -m py_compile bot/strategy/modules/position_manager.py

# 4. Restart bot
nohup python3 run_bot.py > bot_startup.log 2>&1 &

# 5. Verify startup
tail -f bot_live.log | grep -E "(GridBot|initialized|State recovered)"

# 6. Document rollback reason
echo "Phase 0 rolled back at $(date): REASON_HERE" >> deployment_log.txt
```

### Post-Rollback Actions
1. Review logs to identify root cause
2. Fix issue in Phase 0 code
3. Test in staging environment
4. Retry deployment

---

## Success Criteria (48 Hours)

After 48 hours of operation, verify:

✅ **Zero fill queue overflows**
```bash
grep "FILL QUEUE FULL" bot_live.log
# Should return nothing
```

✅ **No deadlocks detected**
```bash
# Check lock logs show clean acquire/release (if DEBUG enabled)
grep "LOCK" bot_live.log | grep -v "Acquired\|Releasing" | wc -l
# Should be 0
```

✅ **State recovery working**
```bash
# Restart bot and check state loads
pkill -SIGTERM -f "python.*run_bot.py"
sleep 10
nohup python3 run_bot.py > bot_startup.log 2>&1 &
tail -50 bot_live.log | grep "State recovered"
# Should show: ✅ State recovered successfully!
```

✅ **Unknown order handling working**
```bash
# Manual test: Place order outside bot, verify reconciliation
grep "TRIGGERING RECONCILIATION" bot_live.log
# Should show reconciliation triggered (if tested)
```

**If all criteria met**: ✅ **Phase 0 deployment SUCCESSFUL** → Proceed to Phase 1 planning

**If any fail**: ⚠️ Investigate and fix before Phase 1

---

## Emergency Contacts

**On-Call Engineer**: [Your Contact Info]  
**Deployment Time**: [Fill in during deployment]  
**Rollback Decision Authority**: [Your Name]

---

## Deployment Log Template

```
=== PHASE 0 DEPLOYMENT LOG ===
Date: November 9, 2025
Time Started: [HH:MM UTC]
Deployed By: [Your Name]

Pre-Deployment Checks:
[ ] Backups verified
[ ] Syntax checks passed
[ ] Current state saved
[ ] Rollback plan ready

Deployment:
[ ] Bot stopped gracefully at: [HH:MM UTC]
[ ] Changes verified in place
[ ] Bot restarted at: [HH:MM UTC]
[ ] Startup logs clean
[ ] All 4 Phase 0 fixes active

Post-Deployment (1 hour):
[ ] Fill queue depth: [X]/1000
[ ] State persistence: Working
[ ] No errors in logs
[ ] Bot trading normally

Post-Deployment (24 hours):
[ ] Fill queue max: [X]/1000
[ ] Persistence events: [X]
[ ] Unknown orders: [X]
[ ] Errors: [X]

Status: [ ] SUCCESS / [ ] ROLLBACK
Notes: [Any observations]

=== END LOG ===
```

---

**Deployment Guide Status**: ✅ READY FOR USE  
**Next Step**: Execute deployment during optimal window (2-4 AM UTC)

---

**End of Phase 0 Deployment Guide**
