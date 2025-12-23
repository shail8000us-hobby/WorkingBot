# 🛑 Bot Shutdown Guide

## Critical Information About Stopping the Bot

### Your Two Recommended Stop Methods

You have **TWO proper ways** to stop the bot - both now support graceful shutdown:

#### Method 1: Tmux Control (RECOMMENDED)
```bash
bash scripts/tmux_control_service.sh stop
```
**Now sends:** SIGTERM → Waits 30s for cleanup → SIGKILL only if needed  
**Result:** ✅ Pending orders cancelled gracefully

#### Method 2: Emergency Kill via WebUI
```bash
curl -X POST http://localhost:5555/api/emergency/kill-all
```
**Now sends:** SIGTERM → Waits 30s for cleanup → SIGKILL only if needed  
**Result:** ✅ Pending orders cancelled gracefully

#### Method 3: Bot Manager Script
```bash
bash bot_manager.sh stop trading
```
**Now sends:** SIGTERM → Waits 30s for cleanup → SIGKILL only if needed  
**Result:** ✅ Pending orders cancelled gracefully

---

### ❌ WRONG WAY (Pending Orders NOT Cancelled)

```bash
kill -9 <PID>     # ❌ IMMEDIATE KILL - No cleanup!
pkill -9 python   # ❌ FORCE KILL - No cleanup!
```

**Problem:** `kill -9` (SIGKILL) **immediately terminates** the process without allowing ANY cleanup code to run. Pending orders will remain active on the exchange!

---

### ✅ MANUAL METHOD (If Needed)

```bash
# Method 1: Graceful signal (RECOMMENDED)
kill <PID>        # ✅ SIGTERM - Triggers cleanup
kill -15 <PID>    # ✅ SIGTERM (same as above)

# Method 2: Interrupt signal
kill -2 <PID>     # ✅ SIGINT (same as Ctrl+C)

# Method 3: Keyboard interrupt (if running in terminal)
Ctrl+C            # ✅ Triggers cleanup
```

**What happens:**
1. Bot receives shutdown signal
2. Signal handler triggers `cleanup()` method
3. **ALL pending BUY orders cancelled** from exchange
4. TP/SELL orders remain active (protect capital)
5. Bot exits gracefully (max 30 seconds)

---

## How Your Recommended Methods Work Now

### Tmux Stop Method
**What changed:**
- ✅ Sends SIGTERM (graceful shutdown)
- ✅ Waits **30 seconds** for cleanup to complete
- ✅ Only uses SIGKILL if process won't die after 30s

**Old behavior (FIXED):**
- ❌ Sent SIGTERM
- ❌ Waited only 3 seconds
- ❌ Then force-killed with SIGKILL

### Emergency Kill Method
**What changed:**
- ✅ Sends SIGTERM to each PID
- ✅ Waits **30 seconds** per process for cleanup
- ✅ Only uses SIGKILL as last resort

**Old behavior (FIXED):**
- ❌ Sent SIGTERM
- ❌ Waited only 0.5 seconds
- ❌ Then immediately force-killed with SIGKILL

---

## How to Stop Your Bot Properly

### Step 1: Use Your Preferred Method

**Option A: Tmux Control (Simplest)**
```bash
bash scripts/tmux_control_service.sh stop
```

**Option B: Emergency Kill via WebUI**
```bash
curl -X POST http://localhost:5555/api/emergency/kill-all
```

**Option C: Bot Manager Script**
```bash
bash bot_manager.sh stop trading
```

**Option D: Manual Kill (Advanced)**
```bash
# Find bot PID
ps aux | grep -E "bot/run|gbot_ws" | grep -v grep

# Stop gracefully
kill <PID>
```

### Step 2: Watch for Cleanup Logs

**Expected Output:**
```
⚠️  Received SIGTERM - Triggering graceful shutdown
🧹 Running cleanup due to signal...
🔍 Fetching all open orders from exchange...
   📊 Found 1 total open orders
   🎯 Found 1 pending BUY orders to cancel
🔥 Cancelling 1 pending BUY order(s)...
   ✅ Cancelled BUY #12345 @ $109,000
✅ Cleanup completed
```

### Step 3: Verify Orders Cancelled

```bash
# Check bot stopped
ps aux | grep -E "bot/run|gbot_ws" | grep -v grep
# (should be empty)

# Check exchange has no pending BUY orders
# (via WebUI or Delta Exchange website)
```

---

## Cleanup Behavior

### What Gets Cancelled
- ✅ **ALL pending BUY orders** (side=buy, not reduce_only)
- ✅ **ALL gridbot orders** waiting in orderbook

### What Stays Active
- ✅ **TP/SELL orders** (reduce_only or side=sell)
- ✅ **Executed positions** (already filled)
- ✅ **Capital protection** orders

**Reason:** TP orders protect your capital by closing positions at profit. Cancelling them would leave positions unprotected!

---

## Shutdown Methods Comparison

| Method | Signal | Wait Time | Cleanup Runs? | Orders Cancelled? | Recommended? |
|--------|--------|-----------|---------------|-------------------|--------------|
| **Tmux Stop** | SIGTERM | 30s | ✅ YES | ✅ YES | ✅ **YES** |
| **Emergency Kill** | SIGTERM | 30s | ✅ YES | ✅ YES | ✅ **YES** |
| **Bot Manager** | SIGTERM | 30s | ✅ YES | ✅ YES | ✅ **YES** |
| `kill <PID>` | SIGTERM | User waits | ✅ YES | ✅ YES | ✅ YES |
| `kill -15 <PID>` | SIGTERM | User waits | ✅ YES | ✅ YES | ✅ YES |
| `kill -2 <PID>` | SIGINT | User waits | ✅ YES | ✅ YES | ✅ YES |
| `Ctrl+C` | SIGINT | User waits | ✅ YES | ✅ YES | ✅ YES |
| `kill -9 <PID>` | SIGKILL | 0s | ❌ NO | ❌ NO | ❌ **NO** |
| `pkill -9` | SIGKILL | 0s | ❌ NO | ❌ NO | ❌ **NO** |

**Key Insight:**
- ✅ **All your methods now wait 30 seconds** for graceful cleanup
- ✅ **Pending orders will be cancelled** before bot exits
- ❌ **Only `kill -9` bypasses cleanup** (never use unless necessary)

---

## Emergency Situations

### If Bot is Frozen/Stuck

```bash
# Try graceful shutdown first
kill <PID>

# Wait 30 seconds for cleanup timeout
sleep 30

# If still running, check process
ps aux | grep <PID>

# Last resort: force kill (accepts pending orders will stay)
kill -9 <PID>

# Manually cancel orders via WebUI or exchange website
```

### If Cleanup Fails

The bot has **3 layers** of cleanup:

1. **Signal Handler** (SIGTERM/SIGINT) - Primary
2. **Finally Block** (in run method) - Backup
3. **Atexit Handler** - Last resort

If all fail:
- Orders remain on exchange
- Check Delta Exchange website
- Manually cancel pending BUY orders
- Keep TP orders active!

---

## Testing Graceful Shutdown

### Quick Test

```bash
# Start bot for 60 seconds
python3 bot/run.py demo 60

# In another terminal, after 10 seconds:
ps aux | grep bot/run
kill <PID>

# Watch for cleanup logs:
# ✅ Should see "Cancelling pending BUY order(s)"
```

### Live Trading Test

```bash
# Get bot PID
ps aux | grep bot/run | grep -v grep | awk '{print $2}'

# Stop gracefully
kill <PID>

# Verify cleanup in logs
tail -50 bot_live.log

# Expected:
# - "Received SIGTERM"
# - "Cancelling pending BUY"
# - "Cleanup completed"
```

---

## Why This Matters

**Before Fix:**
```
❌ User runs: kill -9 18753
❌ Bot dies instantly
❌ Pending BUY @ $109,000 stays on exchange
❌ Market drops to $108,000
❌ Order fills at bad price
❌ User loses money
```

**After Fix:**
```
✅ User runs: kill 18753
✅ Bot receives SIGTERM
✅ Cleanup runs automatically
✅ Pending BUY @ $109,000 cancelled
✅ Position protected
✅ User safe!
```

---

## Best Practices

1. **Always use `kill <PID>` without `-9`**
2. **Never use `kill -9` unless absolutely necessary**
3. **Wait for cleanup to complete** (max 30 seconds)
4. **Verify orders cancelled** after shutdown
5. **Check logs** for cleanup confirmation

---

## Quick Reference

```bash
# ✅ RECOMMENDED: Graceful shutdown
kill $(ps aux | grep bot/run | grep -v grep | awk '{print $2}')

# ✅ ALTERNATIVE: Find and kill gracefully
PID=$(ps aux | grep bot/run | grep -v grep | awk '{print $2}')
kill $PID

# ✅ KEYBOARD: If running in terminal
Ctrl+C

# ❌ AVOID: Force kill (no cleanup)
kill -9 <PID>
```

---

## Summary

| Question | Answer |
|----------|--------|
| **Why didn't pending order cancel when I killed bot?** | Used `kill -9` which bypasses cleanup |
| **Can I use tmux stop?** | ✅ YES - Now waits 30s for cleanup! |
| **Can I use emergency kill?** | ✅ YES - Now waits 30s for cleanup! |
| **What gets cancelled during cleanup?** | ALL pending BUY orders |
| **What stays active?** | TP/SELL orders (protect capital) |
| **How long does cleanup take?** | Max 30 seconds |
| **What if I'm impatient?** | Still wait 30s - your money depends on it! |
| **What if cleanup fails?** | Manually cancel via exchange website |

---

**Document Created:** October 30, 2025  
**Version:** 2.0  
**Related Fixes:**
- ✅ Proactive volatility monitoring (cancels orders when unsafe)
- ✅ Signal handler cleanup (cancels orders on graceful shutdown)
- ✅ Atexit cleanup (last resort fallback)
- ✅ Tmux stop now graceful (30s wait)
- ✅ Emergency kill now graceful (30s wait)
- ✅ Bot manager now graceful (30s wait)
