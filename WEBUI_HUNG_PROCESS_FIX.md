# WebUI Hung Process Fix - Permanent Solution

## Problem
WebUI backend process gets stuck in uninterruptible sleep (state "U"), making localhost unresponsive.

## Root Causes Identified

1. **Blocking SQLite Operations** - Database connections without timeouts
2. **Incorrect Hung Process Detection** - Guardian used wrong psutil constant
3. **Slow Recovery** - Health check threshold too high (3 failures)
4. **Missing State Detection** - Didn't check actual process state via `ps` command

## Fixes Implemented

### 1. Database Timeout Protection ✅
- Added 5-10 second timeouts to ALL SQLite connections
- Files fixed:
  - `webui/backend/app.py` - Startup database check
  - `bot/volatility/delta_volatility_collector.py` - All 6 database operations

### 2. Enhanced Hung Process Detection ✅
- Fixed psutil constant error (`STATUS_UNINTERRUPTIBLE` → `STATUS_DISK_SLEEP`)
- Added dual detection method:
  - **Method 1**: psutil status check (`STATUS_DISK_SLEEP`, `STATUS_LOCKED`)
  - **Method 2**: `ps` command check (detects state "U" directly)
- Detects hung processes within 30 seconds

### 3. Faster Recovery ✅
- Reduced health check threshold from 3 to 2 failures
- Immediate restart if process state is "U" (uninterruptible sleep)
- Immediate restart if process exists but health check fails 2+ times

### 4. Guardian Improvements ✅
- Added `is_process_hung_via_ps()` method for reliable state detection
- Enhanced monitoring loop with multiple detection methods
- Better error handling and logging

## Detection Methods

The Guardian now uses **3 methods** to detect hung processes:

1. **psutil Status Check**: Checks for `STATUS_DISK_SLEEP` or `STATUS_LOCKED`
2. **ps Command Check**: Directly checks process state via `ps -p PID -o state=`
3. **Health Check Failure**: If process exists but health check fails 2+ times

## Auto-Recovery Flow

```
Every 30 seconds:
  1. Check if process is running
  2. Check process state (psutil + ps command)
  3. If state = "U" (uninterruptible sleep) → RESTART
  4. Health check
  5. If health check fails 2+ times → RESTART
  6. Resource monitoring (memory, CPU)
```

## Files Modified

1. `webui/backend/app.py` - Database timeout
2. `bot/volatility/delta_volatility_collector.py` - All SQLite timeouts
3. `webui_guardian.py` - Enhanced hung process detection
4. `setup_webui_auto_recovery.sh` - Setup script

## Verification

```bash
# Check Guardian is running
launchctl list | grep gridbot.webui.guardian

# Check WebUI status
curl http://localhost:5555/api/health

# View Guardian logs
tail -f logs/webui_guardian.log

# Check for hung processes
ps aux | grep "webui/backend/app.py" | grep -v grep
# Should NOT show state "U"
```

## Management

```bash
# Restart Guardian (if needed)
launchctl stop com.gridbot.webui.guardian
launchctl start com.gridbot.webui.guardian

# Re-run setup
./setup_webui_auto_recovery.sh
```

## Expected Behavior

- **Hung Process Detected**: Guardian detects within 30 seconds
- **Auto-Restart**: Process restarted automatically
- **Recovery Time**: < 1 minute from detection to recovery
- **Zero Manual Intervention**: Fully automated

## Status

✅ **FIXED** - All root causes addressed with permanent solutions.

