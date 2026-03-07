# 🚨 CRITICAL: Memory/Disk Space Exhaustion Investigation
**Date:** December 18, 2025  
**Status:** ✅ RESOLVED  
**Severity:** CRITICAL  

---

## Executive Summary

The trading bot accumulated **~80 GB of log files** causing system memory/disk exhaustion on macOS.

**Root Cause:** Infinite error logging loop in `webui_guardian.py` without rate limiting.

**Impact:** 
- System unusable (240GB disk, 165GB used)
- Documents folder: 96.76 GB (mostly logs)
- Trading bot project: 82 GB → **5.3 GB after cleanup**

**Resolution:** 
- Fixed infinite logging bug
- Deleted 77 GB of logs
- Implemented log rotation
- Created emergency cleanup system

---

## 📊 Data Accumulation Breakdown

### Critical Files Found (Before Cleanup)

| File | Size | Location | Issue |
|------|------|----------|-------|
| `webui_guardian_error.log` | **75 GB** | `/logs/` | Infinite logging loop |
| `webui_guardian.log` | **2.0 GB** | `/logs/` | Normal + accumulated errors |
| `pm2-gridbot-live-combined.log` | **1.1 GB** | `/reports/` | PM2 output not rotated |
| `pm2-gridbot-live-error.log` | **1.1 GB** | `/reports/` | PM2 errors not rotated |
| `gridbot-yaml-error.log` | **712 MB** | `/logs/` | Repeated YAML errors |
| `guardian.log` | **407 MB** | `/bot/logs/` | Accumulated guardian logs |
| `launchagent_guardian.log` | **254 MB** | `/bot/logs/` | LaunchAgent output |
| `pm2-guardian-live.log` | **160 MB** | `/bot/logs/` | PM2 guardian output |
| `pm2-guardian-live-out.log` | **159 MB** | `/bot/logs/` | PM2 guardian stdout |
| `metrics.db` | **121 MB** | `/webui/backend/` | Metrics database (OK) |

**Total Log Files:** ~82 GB  
**After Cleanup:** ~5.3 GB  
**Space Freed:** **~77 GB**

---

## 🐛 Root Cause Analysis

### The Infinite Logging Bug

**File:** `webui_guardian.py` (Lines 316-319, 248-250)

```python
# BUG: Monitoring loop without sleep on restart failure
while True:
    try:
        if not self.webui_process or not self.webui_process.is_running():
            log.error("WebUI process died!")  # ← Logged repeatedly
            self.restart_webui(reason="process_died")  # ← Returns False during cooldown
            continue  # ← IMMEDIATELY loops back without sleep!
```

**The restart_webui() method had a cooldown check that returned False immediately:**

```python
def restart_webui(self, reason: str = "manual"):
    time_since_last_restart = time.time() - self.last_restart_time
    
    if time_since_last_restart < RESTART_COOLDOWN:
        log.warning(f"Restart cooldown active...")  # ← Warning logged
        return False  # ← Returns immediately WITHOUT SLEEP!
```

### How It Happened

1. **WebUI process died** (likely due to an error)
2. **Guardian detected death** and tried to restart
3. **Restart failed** (cooldown active or max attempts reached)
4. **Loop continued immediately** without sleep
5. **"WebUI process died!"** logged **~1000 times per second**
6. **Same warning** logged **~1000 times per second**
7. **Over days/weeks:** 75 GB accumulated

**Estimated Log Rate:**
- ~100 bytes per error message
- ~2000 messages per second (error + warning)
- ~200 KB/second
- **~17 GB per day!**

**This explains the 75 GB file** - likely ran for 4-5 days continuously.

---

## ✅ Fixes Implemented

### 1. Fixed Infinite Loop in webui_guardian.py

**Change #1: Added sleep in restart cooldown**
```python
def restart_webui(self, reason: str = "manual"):
    if time_since_last_restart < RESTART_COOLDOWN:
        cooldown_remaining = int(RESTART_COOLDOWN - time_since_last_restart)
        log.warning(f"Restart cooldown active ({cooldown_remaining}s remaining) - sleeping...")
        time.sleep(min(cooldown_remaining, 10))  # FIXED: Sleep to prevent spam
        return False
```

**Change #2: Added sleep after failed restart in main loop**
```python
if not self.webui_process or not self.webui_process.is_running():
    log.error("WebUI process died!")
    self.restart_webui(reason="process_died")
    time.sleep(10)  # FIXED: Always sleep after restart attempt
    continue
```

### 2. Implemented Log Rotation

**Added rotating file handler for error logs:**
```python
import logging.handlers

error_handler = logging.handlers.RotatingFileHandler(
    PROJECT_ROOT / 'logs' / 'webui_guardian_error.log',
    maxBytes=100*1024*1024,  # 100MB max
    backupCount=3  # Keep 3 backups
)
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)
```

**Benefits:**
- Error logs automatically rotate at 100MB
- Keeps only 3 backups (max 400MB total)
- Prevents unbounded growth

### 3. Created Emergency Cleanup System

**New File:** `emergency_log_cleanup.py`

**Features:**
- Automatically deletes logs > 500MB
- Removes error logs > 100MB
- Cleans PM2 logs > 100MB
- Removes old database backups (>30 days)
- Deletes old event databases
- Logs all cleanup actions

**Usage:**
```bash
# Manual run
python3 emergency_log_cleanup.py

# Schedule with cron (every 30 minutes)
*/30 * * * * cd /Users/ssr/Projects/WorkingBot && python3 emergency_log_cleanup.py
```

---

## 📈 Other Data Sources (Non-Critical)

### Database Growth (Expected Behavior)
- `bot_events.db`: Growing as designed (120K+ events)
- Already addressed with [database cleanup fix](MEMORY_FIX_DEC18_2025.md)
- Automatic cleanup every 6 hours (keeps last 7 days)

### Node Modules Cache (~340MB)
- `webui/frontend/node_modules/.cache/`: 340MB
- **Action:** Normal build cache, can be deleted if needed
- **Regenerates:** Automatically on next build

### Git Repository (~1.2GB)
- `.git/objects/pack/`: 830MB
- `.git/cursor/crepe/`: 500MB (Cursor AI cache)
- **Action:** Consider `git gc --aggressive` if needed
- **Not urgent:** Git objects are compressed

---

## 🎯 Prevention Measures

### Immediate Actions Taken
1. ✅ Fixed infinite logging bug in webui_guardian.py
2. ✅ Deleted 77 GB of accumulated logs
3. ✅ Implemented log rotation (100MB limits)
4. ✅ Created emergency cleanup script

### Recommended: Scheduled Cleanup

**Add to crontab:**
```bash
# Edit crontab
crontab -e

# Add this line (runs every 30 minutes)
*/30 * * * * cd /Users/ssr/Projects/WorkingBot && /usr/bin/python3 emergency_log_cleanup.py >> /tmp/log_cleanup.log 2>&1
```

### Monitoring Recommendations

**1. Disk Space Monitoring**
```bash
# Check weekly
df -h /

# Check project size
du -sh /Users/ssr/Projects/WorkingBot
```

**2. Large Log Detection**
```bash
# Find logs > 100MB
find /Users/ssr/Projects/WorkingBot -name "*.log" -size +100M -exec ls -lh {} \;
```

**3. Process Monitoring**
```bash
# Check if webui_guardian is running properly
ps aux | grep webui_guardian

# Check error log growth
ls -lh logs/webui_guardian_error.log*
```

---

## 🔍 Why This Happened

### Design Flaw Analysis

The guardian script had a **conceptual flaw**:

1. **Assumption:** Restart will either succeed or fail, then continue monitoring
2. **Reality:** Restart can fail but loop continues immediately
3. **Missing:** Rate limiting or sleep on failure path
4. **Result:** Infinite loop logging at ~1000 msg/sec

### Contributing Factors

1. **No log rotation:** Python logging wasn't configured with RotatingFileHandler
2. **No disk monitoring:** No alerts when disk space low
3. **No rate limiting:** No throttling on error logging
4. **No max file size:** Nothing stopped log files from growing
5. **PM2 logs not rotated:** PM2 wasn't configured with log rotation

---

## 📋 Verification Checklist

- [x] webui_guardian.py bug fixed
- [x] Log rotation implemented
- [x] Emergency cleanup script created
- [x] 77 GB of logs deleted
- [x] Project size reduced to 5.3 GB
- [x] Database cleanup already implemented (previous fix)
- [x] All critical files documented
- [ ] Schedule cron job for automatic cleanup (user action required)
- [ ] Monitor disk space for next 24-48 hours
- [ ] Verify webui_guardian logs stay < 100MB

---

## 🎓 Lessons Learned

1. **Always add sleep in error loops** - Even if restart "should" succeed
2. **Use RotatingFileHandler** - For all production logs
3. **Monitor disk space** - Before it becomes critical
4. **Rate limit error logging** - Prevent log bombs
5. **Test failure modes** - What happens when restart fails repeatedly?
6. **Add circuit breakers** - Stop trying after N failures
7. **Monitor file sizes** - Alert on > threshold

---

## 📞 Support & Maintenance

**If logs grow again:**
1. Run: `python3 emergency_log_cleanup.py`
2. Check: `ps aux | grep webui_guardian`
3. Review: `tail -100 logs/webui_guardian_error.log`
4. Restart if needed: Kill and restart guardian

**If disk fills up:**
1. Run emergency cleanup
2. Check for new large files: `find . -size +500M`
3. Empty trash: `rm -rf ~/.Trash/*`
4. Clear node_modules cache if needed

---

## ✅ Resolution Status

**STATUS:** ✅ **RESOLVED**

**Fixes Applied:**
- Code fix: Prevents infinite logging loop
- Log rotation: Limits error log to 400MB max
- Emergency cleanup: Manual intervention available
- Documentation: Complete investigation recorded

**Disk Space:**
- Before: 165.5 GB / 245.11 GB (67% full)
- After: ~88 GB / 245.11 GB (36% full) - estimated
- Freed: ~77 GB

**Project Size:**
- Before: ~82 GB
- After: 5.3 GB
- Reduction: **93.5%**

---

**Investigation completed by:** GitHub Copilot  
**Date:** December 18, 2025  
**Report:** CRITICAL_MEMORY_ISSUE_INVESTIGATION_DEC18_2025.md
