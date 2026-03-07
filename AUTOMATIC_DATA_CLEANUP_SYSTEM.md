# AUTOMATIC DATA CLEANUP SYSTEM
## 48-Hour Retention Policy

**Date:** December 18, 2025  
**Status:** ✅ ACTIVE & RUNNING

---

## 🎯 OVERVIEW

Comprehensive automatic cleanup system that prevents disk bloat by removing ALL bot data older than 48 hours (2 days). This system ensures the disk space issue **never occurs again**.

### What Gets Cleaned:
- ✅ **Log files** older than 48 hours
- ✅ **Database records** older than 48 hours (events, metrics, PnL, errors)
- ✅ **Volatility data** by SIZE (500MB limit) - oldest records deleted when limit exceeded
- ✅ **Backup files** older than 7 days
- ✅ **Cache files** older than 24 hours
- ✅ **Temporary files** and Python bytecode

### Retention Periods:
- **Primary Data:** 2 days (48 hours)
- **Volatility Data:** Size-based (500MB limit) - NOT time-based
- **Backups:** 7 days
- **Cache:** 1 day

---

## 🛠️ SYSTEM COMPONENTS

### 1. Auto Data Cleanup Script
**File:** `auto_data_cleanup.py`

**Features:**
- Cleans logs, databases, backups, and cache automatically
- Runs every hour via LaunchAgent
- Detailed logging of all cleanup operations
- Safe deletion with error handling
- Database VACUUM to reclaim space

**Usage:**
```bash
# Run once
python3 auto_data_cleanup.py --once

# Run continuously (every hour)
python3 auto_data_cleanup.py

# Custom retention period (3 days)
python3 auto_data_cleanup.py --retention-days 3
```

### 2. Event Retention Policy
**File:** `bot/strategy/modules/event_retention.py`

**Updated to 48-hour retention:**
- Guardian signals cleaned every hour
- Automatic VACUUM when >1000 records deleted
- Runs alongside bot processes

### 3. LaunchAgent Auto-Start
**File:** `~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist`

**Configuration:**
- Runs every hour (`StartInterval: 3600`)
- Auto-starts on system boot (`RunAtLoad: true`)
- Throttled restarts (`ThrottleInterval: 60`)

**Commands:**
```bash
# Check status
launchctl list | grep cleanup

# Start
launchctl load ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist

# View logs
tail -f logs/auto_cleanup.log
```

---

## 📊 DATABASES MANAGED

### 1. **bot_events_LONG.db** (~14MB)
- **Table:** `events`
- **Cleanup:** Events older than 48 hours deleted
- **Frequency:** Every hour

### 2. **gridbot_events.db** (~3MB)
- **Table:** `events`
- **Cleanup:** Events older than 48 hours deleted
- **Frequency:** Every hour

### 3. **data/volatility.db** (~54MB)
- **Table:** `volatility_data`
- **Cleanup:** Size-based management (500MB limit)
- **Strategy:** When exceeds 500MB, oldest 30% of records deleted
- **Frequency:** Checked every hour
- **Note:** NOT subject to 48-hour deletion - kept for long-term analysis

### 4. **webui/backend/metrics.db** (~128MB → cleaned)
- **Table:** `api_metrics`
- **Cleanup:** Metrics older than 48 hours deleted
- **Frequency:** Every hour
- **Note:** Largest database - most critical for space management

### 5. **bot/state/events.db** (~8MB)
- **Table:** `pnl_history`
- **Cleanup:** PnL history older than 48 hours deleted
- **Frequency:** Every hour

### 6. **data/errors.db** (~12KB)
- **Table:** `errors`
- **Cleanup:** Error logs older than 48 hours deleted
- **Frequency:** Every hour

---

## 📝 LOG FILES WITH ROTATION

All logging now uses `RotatingFileHandler` to prevent unbounded growth:

### Fixed Files:
1. ✅ `webui_guardian.py` - 10MB max, 2 backups
2. ✅ `bot/guardian/core/guardian_bot.py` - 10MB max, 3 backups
3. ✅ `liquidation_monitor.py` - 10MB max, 3 backups
4. ✅ `auto_data_cleanup.py` - 5MB max, 2 backups
5. ✅ `disk_health_monitor.py` - 5MB max, 2 backups

### Log Rotation Settings:
- **Max file size:** 5-10MB per file
- **Backup count:** 2-3 files
- **Total max per logger:** 15-30MB
- **Old logs auto-deleted:** After 48 hours

---

## 🔄 CLEANUP SCHEDULE

### Hourly (via LaunchAgent):
```
00:00 → Cleanup runs
01:00 → Cleanup runs
02:00 → Cleanup runs
... (every hour)
```

### What Happens Each Hour:
1. **Scan logs** → Delete files older than 48 hours
2. **Scan databases** → Delete records older than 48 hours
3. **Run VACUUM** → Reclaim freed space (if significant deletion)
4. **Scan backups** → Delete backups older than 7 days
5. **Scan cache** → Delete cache files older than 24 hours
6. **Log results** → Record cleanup statistics

---

## 📈 MONITORING

### Check Cleanup Status:
```bash
# View latest cleanup log
tail -50 logs/auto_cleanup.log

# Check LaunchAgent status
launchctl list | grep cleanup

# Manual cleanup test
python3 auto_data_cleanup.py --once

# Disk health check
python3 disk_health_monitor.py
```

### Cleanup Statistics:
```
2025-12-18 14:07:39 - ✅ CLEANUP COMPLETED
   Duration: 10.27s
   Logs removed: 52 (10.33MB)
   DB records deleted: 11,085
   DB space freed: 16.09MB
   Backups removed: 2 (26.36MB)
   Cache files removed: 4
   Total space freed: 52.78MB
```

---

## 🚨 ALERTS & THRESHOLDS

### Disk Space Monitoring:
```python
MAX_DISK_USAGE_PERCENT = 80  # Alert if disk exceeds 80%
MAX_LOG_SIZE_MB = 50         # Alert if any log exceeds 50MB
MAX_TOTAL_LOGS_GB = 2        # Alert if total logs exceed 2GB
```

### Auto-Actions:
- **Disk >80%:** Emergency cleanup triggered
- **Log >50MB:** File truncated to last 1MB
- **Total logs >2GB:** Aggressive cleanup of all old files

---

## 🔧 CUSTOMIZATION

### Change Retention Period:
Edit `auto_data_cleanup.py`:
```python
DEFAULT_RETENTION_DAYS = 2  # Change to desired days
LOG_RETENTION_DAYS = 2
DATABASE_RETENTION_DAYS = 2
BACKUP_RETENTION_DAYS = 7

# Volatility database managed by size, not time
MAX_VOLATILITY_SIZE_MB = 500  # Change to desired MB
```

### Change Cleanup Frequency:
Edit `~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist`:
```xml
<key>StartInterval</key>
<integer>3600</integer>  <!-- Change to desired seconds -->
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist
```

---

## ✅ VERIFICATION

### Current Status (Dec 18, 2025):
```
✅ Disk usage: 7% (11GB / 228GB)
✅ Log directory: 38MB (down from 100GB+)
✅ Auto-cleanup: RUNNING (PID 14596)
✅ Databases: All under control
✅ Log rotation: Active on all files
✅ LaunchAgent: Loaded and running
```

### Test Cleanup:
```bash
# Run manual cleanup
python3 auto_data_cleanup.py --once

# Check results
cat logs/auto_cleanup.log | tail -20

# Verify disk space
df -h /
du -sh logs/ data/ *.db
```

---

## 🎯 PREVENTION MEASURES

### 1. **Rotating File Handlers** 
All logging uses `RotatingFileHandler` with strict size limits.

### 2. **48-Hour Retention**
All data auto-deleted after 48 hours - no manual intervention needed.

### 3. **Hourly Cleanup**
LaunchAgent runs cleanup every hour automatically.

### 4. **Database VACUUM**
Automatic space reclamation after record deletion.

### 5. **Backup Management**
Old backups (>7 days) automatically removed.

### 6. **Error Throttling**
Same errors logged max once per minute to prevent spam.

### 7. **Health Monitoring**
`disk_health_monitor.py` can run continuously to alert on issues.

---

## 📋 MAINTENANCE

### Daily Tasks:
- None required - fully automatic!

### Weekly Review (Optional):
```bash
# Check cleanup logs
tail -100 logs/auto_cleanup.log

# Verify disk space
df -h / && du -sh logs/ data/
```

### Monthly Review (Optional):
```bash
# Check database sizes
du -h *.db data/*.db bot/state/*.db webui/backend/*.db

# Review retention policy
python3 auto_data_cleanup.py --once
```

---

## 🔗 RELATED FILES

### Cleanup System:
- `auto_data_cleanup.py` - Main cleanup script
- `disk_health_monitor.py` - Health monitoring
- `~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist` - Auto-start

### Fixed Logging:
- `webui_guardian.py` - WebUI guardian with rotation
- `bot/guardian/core/guardian_bot.py` - Guardian bot with rotation
- `liquidation_monitor.py` - Liquidation monitor with rotation

### Retention Policies:
- `bot/strategy/modules/event_retention.py` - Event retention (48h)

### Documentation:
- `DISK_BLOAT_FIX_DEC18_2025.md` - Root cause analysis
- `AUTOMATIC_DATA_CLEANUP_SYSTEM.md` - This file

---

## 💡 KEY BENEFITS

1. **No manual cleanup needed** - Fully automatic
2. **Prevents disk bloat** - 48-hour retention ensures fresh data
3. **Space efficient** - Old data removed hourly
4. **Database optimization** - Automatic VACUUM
5. **Comprehensive** - Handles logs, databases, backups, cache
6. **Monitored** - Detailed logging of all operations
7. **Safe** - Error handling prevents data loss
8. **Configurable** - Easy to adjust retention periods

---

## 🚀 GETTING STARTED

### Verify System is Running:
```bash
# Check LaunchAgent
launchctl list | grep cleanup

# View latest cleanup
tail -20 logs/auto_cleanup.log

# Check disk space
df -h / && du -sh logs/
```

### Everything is automatic! 🎉
The system runs every hour without any manual intervention required.

---

**Created:** December 18, 2025  
**Last Updated:** December 18, 2025  
**Status:** ✅ ACTIVE & RUNNING  
**Next Cleanup:** Every hour (automatic)
