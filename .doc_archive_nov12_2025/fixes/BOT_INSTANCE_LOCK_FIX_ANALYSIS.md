# Bot Instance Lock Issue - Root Cause Analysis & Permanent Fix

**Date:** November 9, 2025  
**Issue:** Bot restarted 27 times by PM2, then stopped working  
**Severity:** 🚨 CRITICAL - Could cause missed trades or duplicate positions

---

## 🔍 Root Cause Analysis

### What Happened

1. **Two bots were running simultaneously:**
   - Bot #1 (PID 55251): Started manually via `python -m bot.run` at 17:25
   - Bot #2 (PM2): Trying to start but blocked by instance lock

2. **PM2 restart loop:**
   - PM2 tries to start → Finds lock file with PID 55251
   - Bot checks if PID 55251 exists → YES (it's running!)
   - Bot exits with "Another instance already running"
   - PM2 waits, then tries again → REPEAT 27 times
   - PM2 gives up after too many failures

3. **Lock mechanism working correctly:**
   - The single_instance_lock system DID ITS JOB
   - It prevented duplicate bots (which would be catastrophic)
   - The problem was: two different methods of starting the bot

### Why This is Dangerous in Trading

**If two bots run simultaneously:**
- ❌ Double orders placed
- ❌ Double positions opened  
- ❌ Conflicting take-profit orders
- ❌ Race conditions in state management
- ❌ Corrupted runtime_state.json
- ❌ Accounting errors
- ❌ **POTENTIAL SIGNIFICANT LOSSES**

**Good news:** The lock system prevented this disaster!

---

## ✅ Permanent Fix Implemented

### 1. Enhanced Lock Validation

**File:** `bot/safety/single_instance_lock.py`

**Improvement:** Added process command verification

```python
# Old behavior:
- Check if PID exists → assume it's valid

# New behavior:
- Check if PID exists
- Verify it's actually a bot process (check command line)
- Prevents false positives from recycled PIDs
```

**Benefit:** More robust detection of stale locks

### 2. Fix Script Created

**File:** `fix_bot_instance_lock.sh`

**Features:**
- Detects all running bot instances (PM2 and standalone)
- Identifies conflicts
- Cleans up stale lock files
- Kills standalone processes (with confirmation)
- Resets PM2 restart counter
- Verifies final state

**Usage:**
```bash
./fix_bot_instance_lock.sh
```

### 3. Prevention Guidelines

**Added to documentation:**

✅ **ALWAYS start bot via PM2:**
```bash
./pm2_gridbot.sh start live
```

❌ **NEVER start bot directly:**
```bash
python -m bot.run  # DON'T DO THIS!
python bot_launcher.py  # DON'T DO THIS!
```

---

## 🛡️ How to Prevent Future Issues

### Rule #1: Use PM2 Exclusively

```bash
# Start
./pm2_gridbot.sh start live

# Stop
./pm2_gridbot.sh stop live

# Restart
./pm2_gridbot.sh restart live

# Status
pm2 status

# Logs
pm2 logs gridbot-live
```

### Rule #2: Check Before Starting

```bash
# Always check first
ps aux | grep "bot.run" | grep -v grep

# If anything shows up, investigate before starting PM2
```

### Rule #3: Monitor Restart Count

```bash
# Check restart count regularly
pm2 status

# If restarts > 5, investigate immediately
pm2 logs gridbot-live --lines 100
```

### Rule #4: Save PM2 State

```bash
# After starting bot successfully
pm2 save

# This ensures PM2 remembers your config
# Useful after system reboots
```

---

## 🔧 Troubleshooting Guide

### Issue: "Another instance already running"

```bash
# Step 1: Check what's running
ps aux | grep -E "bot.run|bot_launcher" | grep -v grep

# Step 2: Check lock files
ls -la .bot_instance*.lock
cat .bot_instance_live.lock  # Check PID

# Step 3: Verify PID
ps -fp <PID_FROM_LOCK_FILE>

# Step 4: If stale, remove lock
rm .bot_instance_live.lock

# Step 5: Restart
./pm2_gridbot.sh restart live
```

### Issue: High Restart Count in PM2

```bash
# Step 1: Check why it's restarting
pm2 logs gridbot-live --lines 200 --err

# Step 2: Common causes:
# - Lock file issues → Run fix_bot_instance_lock.sh
# - Config errors → Check grid_config.env
# - Memory issues → Check system resources
# - API issues → Check Delta Exchange status

# Step 3: Reset counter after fixing
pm2 reset gridbot-live
```

### Issue: Two Bots Running

```bash
# EMERGENCY: Kill all bots immediately
pkill -f "bot.run"
pkill -f "bot_launcher"
pm2 stop all

# Then start properly
./fix_bot_instance_lock.sh
```

---

## 📊 Lock File Format

**Location:** `.bot_instance_live.lock` (for live mode)

**Content:**
```
55251                    # PID of running bot
1699548906.123          # Unix timestamp
2025-11-09 17:25:06     # Human-readable time
```

**Validation:**
1. Check if PID exists: `ps -p <PID>`
2. Verify it's a bot: `ps -fp <PID> | grep bot`
3. If both pass: lock is valid
4. If either fails: lock is stale (safe to remove)

---

## 🚨 Emergency Procedures

### If Bot Crashes in Production

```bash
# 1. Check status
pm2 status

# 2. Check logs for errors
pm2 logs gridbot-live --lines 50 --err

# 3. If restart loop detected
./fix_bot_instance_lock.sh

# 4. Monitor restart
pm2 logs gridbot-live

# 5. If stable, save state
pm2 save
```

### If Duplicate Positions Detected

```bash
# 1. STOP ALL BOTS IMMEDIATELY
pm2 stop all
pkill -f bot.run

# 2. Check for multiple instances
ps aux | grep bot | grep -v grep

# 3. Clean all locks
rm -f .bot_instance*.lock

# 4. Verify positions on exchange
# (Manual check via Delta Exchange UI)

# 5. Start ONLY via PM2
./pm2_gridbot.sh start live

# 6. Monitor carefully
pm2 logs gridbot-live
```

---

## ✅ Verification Checklist

After running the fix, verify:

- [ ] Only ONE bot process running
- [ ] Bot process is child of PM2
- [ ] PM2 status shows "online"
- [ ] Restart count reset to 0
- [ ] Lock file exists with correct PID
- [ ] Logs show normal operation
- [ ] No "Another instance" errors
- [ ] Positions are correct on exchange

```bash
# Quick verification command
pm2 status && \
ps aux | grep bot.run | grep -v grep && \
cat .bot_instance_live.lock && \
pm2 logs gridbot-live --lines 10 --nostream
```

---

## 📚 Related Files

- `bot/safety/single_instance_lock.py` - Lock mechanism (ENHANCED)
- `fix_bot_instance_lock.sh` - Fix script (NEW)
- `pm2_gridbot.sh` - PM2 management script
- `ecosystem.gridbot.config.js` - PM2 configuration
- `.bot_instance_live.lock` - Lock file (live mode)
- `.bot_instance_demo.lock` - Lock file (demo mode)

---

## 💡 Lessons Learned

1. **Single-instance lock is CRITICAL** - It prevented a disaster
2. **Always use process managers** - PM2, systemd, etc.
3. **Never mix startup methods** - Stick to ONE way
4. **Monitor restart counts** - Early warning system
5. **Lock validation works** - The system did its job

---

**Status:** ✅ FIXED  
**Tested:** ✅ YES  
**Deployed:** ✅ YES  
**Documented:** ✅ YES

**Next Review:** Monitor for 24 hours, check restart count stays at 0
